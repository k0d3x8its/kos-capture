"""
screens/ingest.py

Ingest screen — drives kos-ingest via the claude CLI in non-interactive
stream-json mode with bidirectional stdin/stdout.

Flow:
  1. Spawns `claude --print --input-format stream-json --output-format stream-json
     --verbose` with cwd=vault_root
  2. Sends /kos-ingest as a JSON user message via stdin
  3. Reads JSON events from stdout:
       - assistant / text blocks  → prose lines in RichLog
       - assistant / tool_use     → "Reading …" / "Wrote …" etc.
       - result / is_error=true   → red error
  4. Input bar stays unlocked throughout — user can reply to claude at any time;
     replies are written back to claude's stdin as JSON user messages.
  5. On result event or EOF → marks complete, locks input, unlocks Escape.

Escape is blocked while ingest is in progress.
Each IngestScreen instance is pushed fresh by ReadyScreen — vault_root is
passed via the constructor.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

# Model-id → friendly display name
_MODEL_NAMES: dict[str, str] = {
    "claude-opus-4-7":             "Opus 4.7",
    "claude-sonnet-4-6":           "Sonnet 4.6",
    "claude-haiku-4-5-20251001":   "Haiku 4.5",
    "claude-opus-4-5":             "Opus 4.5",
    "claude-sonnet-4-5":           "Sonnet 4.5",
    "claude-3-5-sonnet-20241022":  "Sonnet 3.5",
    "claude-3-opus-20240229":      "Opus 3",
    "claude-3-haiku-20240307":     "Haiku 3",
}

def _friendly_model(model_id: str) -> str:
    for key, name in _MODEL_NAMES.items():
        if key in model_id:
            return name
    return model_id

import rich.box as _rich_box
from rich.markup import escape as _rich_escape
from rich.table import Table as _RichTable

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, LoadingIndicator, RichLog, Static



# ── ANSI stripping ─────────────────────────────────────────────────────────────

_ANSI_RE = re.compile(
    r"\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]"  # CSI sequences (any params)
    r"|\x1b\][^\x07]*\x07"                           # OSC sequences
    r"|\x1b[()][AB012]"                               # charset selection
    r"|\x1b[=>MDE78]"                                 # misc single-char escapes
    r"|\x0f|\x0e"                                     # SI / SO shift
    r"|\r"                                            # bare carriage return
)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


# ── Line formatter ─────────────────────────────────────────────────────────────

_READ_RE     = re.compile(r"^(Reading|Searching|Fetching|Checking|Scanning|Loading|Listing|Running)\b")
_WRITE_RE    = re.compile(r"^(Wrote|Created|Updated|Saved|Writing|Moved|Renamed|Editing)\b")
_ERR_RE      = re.compile(r"\b(Error|Failed|Warning|Exception|Traceback)\b", re.IGNORECASE)
_QUESTION_RE = re.compile(r"\?\s*$")
_NUM_LIST_RE     = re.compile(r"^(\d+)(\.)(\s+)")
_BOLD_MD_RE      = re.compile(r"\*\*(.+?)\*\*")
_TITLE_HYPHEN_RE = re.compile(
    r"^(.{1,40}?)\s+(-)\s+"              # hyphen-minus: flexible label length
    r"|"
    r"^(\S+(?:\s+\S+)?)\s+([–—])\s+"    # em/en-dash: ≤2-word label only
)
_WARN_MD_RE      = re.compile(r"^\*\*Warning:\*\*\s*(.*)", re.IGNORECASE)
_MD_HEADING_RE   = re.compile(r"^(#{1,3})\s+(.+)")
_DATE_RE         = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
_CODE_SPAN_RE    = re.compile(r"`([^`]+)`")

# Matches dir/file.ext OR bare known-extension filename.
# Two alternatives share the regex so both are handled in one pass.
_PATH_COLOR_RE = re.compile(
    r"((?:[\w.\-]+/)+)([\w.\-]+\.[a-zA-Z]{2,6})"            # alt 1: dir/file.ext
    r"|"
    r"(?<![/\w])([\w\-]{2,}\.(?:md|pdf|txt|json|yaml|yml"   # alt 2: bare file
    r"|py|js|ts|sh|log|csv|mp3|mp4|wav|m4a))\b"
)

# Set by IngestScreen._begin() so path display starts at vault root name.
_vault_root_display: Path | None = None


def _truncate_to_vault(path_str: str) -> str:
    """Strip absolute prefix so display begins at vault root directory name."""
    if _vault_root_display is None:
        return path_str
    try:
        return str(Path(path_str).relative_to(_vault_root_display.parent))
    except ValueError:
        return path_str


def _apply_inline_md(escaped: str) -> str:
    """Replace **text** with highlighted markup in an already-escaped string."""
    return _BOLD_MD_RE.sub(r"[bold #F4A261]\1[/bold #F4A261]", escaped)


def _apply_date_highlights(safe: str) -> str:
    """Color dates in M/D/YY or MM/DD/YYYY format bright yellow."""
    return _DATE_RE.sub(r"[bold #FFD700]\1[/bold #FFD700]", safe)


def _apply_code_highlights(safe: str) -> str:
    """Highlight `code spans` — light blue text on dark navy background."""
    return _CODE_SPAN_RE.sub(
        lambda m: f"[bold #9CDCFE on #1E2832]{m.group(1)}[/bold #9CDCFE on #1E2832]",
        safe,
    )


def _apply_path_highlights(safe: str) -> str:
    """Color directories dim cyan and filenames bold cyan within escaped prose."""
    def _replace(m: re.Match) -> str:
        if m.group(1) is not None:   # dir/file.ext
            return (
                f"[dim cyan]{m.group(1)}[/dim cyan]"
                f"[bold cyan]{m.group(2)}[/bold cyan]"
            )
        return f"[bold cyan]{m.group(3)}[/bold cyan]"  # bare filename
    return _PATH_COLOR_RE.sub(_replace, safe)


_MD_TABLE_CELL_SEP_RE = re.compile(r"^[-:\s]+$")


def _render_md_table(rows: list[str]) -> "_RichTable | None":
    """Parse buffered Markdown table rows into a Rich Table renderable.

    Returns None when the buffer is too short or has no separator row.
    """
    def _parse_row(raw: str) -> list[str]:
        cells = raw.split("|")
        if cells and not cells[0].strip():
            cells = cells[1:]
        if cells and not cells[-1].strip():
            cells = cells[:-1]
        return [c.strip() for c in cells]

    parsed = [_parse_row(r) for r in rows if r.strip()]
    if len(parsed) < 2:
        return None

    sep_idx = next(
        (i for i, row in enumerate(parsed)
         if row and all(_MD_TABLE_CELL_SEP_RE.match(c) for c in row)),
        None,
    )
    if sep_idx is None or sep_idx == 0:
        return None

    headers   = parsed[0]
    data_rows = parsed[sep_idx + 1:]
    n_cols    = len(headers)
    if n_cols == 0:
        return None

    table = _RichTable(
        box=_rich_box.SIMPLE_HEAD,
        header_style="bold #C084FC",
        border_style="dim #5BC8C8",
        show_edge=False,
        padding=(0, 1),
    )
    for h in headers:
        table.add_column(
            _apply_inline_md(_apply_code_highlights(_rich_escape(h))),
            style="#F4A261",
        )
    for row in data_rows:
        if not any(row):
            continue
        padded = (row + [""] * n_cols)[:n_cols]
        table.add_row(*[
            _apply_inline_md(_apply_code_highlights(_rich_escape(c)))
            for c in padded
        ])

    return table


def _fmt_ingest_line(line: str) -> str:
    """Apply Rich markup; all brackets escaped first to prevent MarkupError."""
    safe = _rich_escape(line)
    # Tool-action tiers take full priority over prose coloring.
    if _WRITE_RE.search(line):
        return f"[green]{safe}[/green]"
    if _READ_RE.search(line):
        return f"[dim cyan]{safe}[/dim cyan]"
    # **Warning:** gets split: bright-red bold title + burnt-red body.
    wm = _WARN_MD_RE.match(line)
    if wm:
        body_safe = _apply_date_highlights(_apply_path_highlights(_apply_code_highlights(_apply_inline_md(_rich_escape(wm.group(1))))))
        return (
            f"[bold #FF1744]Warning:[/bold #FF1744] "
            f"[#C62828]{body_safe}[/#C62828]"
        )
    # Markdown headings (###/##/#): strip hashes then apply title-hyphen split.
    hm = _MD_HEADING_RE.match(line)
    if hm:
        heading_text = hm.group(2)
        th2 = _TITLE_HYPHEN_RE.match(heading_text)
        if th2:
            label_raw = th2.group(1) if th2.group(1) is not None else th2.group(3)
            sep_char  = th2.group(2) if th2.group(2) is not None else th2.group(4)
            label_safe = _apply_date_highlights(_apply_path_highlights(_apply_code_highlights(_apply_inline_md(_rich_escape(label_raw)))))
            rest_safe  = _apply_date_highlights(_apply_path_highlights(_apply_code_highlights(_apply_inline_md(_rich_escape(heading_text[th2.end():])))))
            sep = _rich_escape(sep_char)
            return (
                f"[bold #C084FC]{label_safe}[/bold #C084FC]"
                f"[dim] {sep} [/dim]"
                f"[#A8D8EA]{rest_safe}[/#A8D8EA]"
            )
        label_safe = _apply_date_highlights(_apply_path_highlights(_apply_code_highlights(_apply_inline_md(_rich_escape(heading_text)))))
        return f"[bold #C084FC]{label_safe}[/bold #C084FC]"
    # Title-hyphen: checked before _ERR_RE so "Issue N - Failed …" gets the
    # structured split instead of being swallowed as a plain error line.
    th = _TITLE_HYPHEN_RE.match(line)
    if th:
        # Alt 1 (hyphen-minus): groups 1,2 — Alt 2 (em/en-dash): groups 3,4
        label_raw = th.group(1) if th.group(1) is not None else th.group(3)
        sep_char  = th.group(2) if th.group(2) is not None else th.group(4)
        label_safe = _apply_date_highlights(_apply_path_highlights(_apply_code_highlights(_apply_inline_md(_rich_escape(label_raw)))))
        rest_safe  = _apply_date_highlights(_apply_path_highlights(_apply_code_highlights(_apply_inline_md(_rich_escape(line[th.end():])))))
        sep = _rich_escape(sep_char)
        return (
            f"[bold #C084FC]{label_safe}[/bold #C084FC]"
            f"[dim] {sep} [/dim]"
            f"[#A8D8EA]{rest_safe}[/#A8D8EA]"
        )
    if _ERR_RE.search(line):
        return f"[red]{safe}[/red]"
    # Apply inline markdown, path highlights, and date highlights before color tiers.
    safe = _apply_inline_md(safe)
    safe = _apply_code_highlights(safe)
    safe = _apply_path_highlights(safe)
    safe = _apply_date_highlights(safe)
    # Numbered list: applied before question check so "1. Is this?" gets
    # purple number AND orange question color.
    safe = _NUM_LIST_RE.sub(
        lambda n: (
            f"[bold #C084FC]{n.group(1)}[/bold #C084FC]"
            f"[dim]{n.group(2)}[/dim]"
            f"{n.group(3)}"
        ),
        safe,
    )
    # Questions pop in bright orange.
    if _QUESTION_RE.search(line):
        return f"[#FF6B35]{safe}[/#FF6B35]"
    # All other Claude prose in light orange.
    return f"[#F4A261]{safe}[/#F4A261]"


# ── Tool-use → human-readable ──────────────────────────────────────────────────

_TOOL_VERB: dict[str, str] = {
    "Read":         "Reading",
    "Write":        "Wrote",
    "Edit":         "Editing",
    "MultiEdit":    "Editing",
    "Bash":         "Running",
    "Glob":         "Listing",
    "Grep":         "Searching",
    "WebFetch":     "Fetching",
    "WebSearch":    "Searching",
    "NotebookRead": "Reading",
    "NotebookEdit": "Editing",
}


def _fmt_tool_use(name: str, tool_input: dict) -> str:
    verb = _TOOL_VERB.get(name, name)
    target = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("pattern")
        or tool_input.get("query")
        or (str(tool_input.get("command", ""))[:70] if tool_input.get("command") else "")
        or ""
    )
    return f"{verb}  {target}" if target else verb


# ── Tool-use → Rich markup (dir/file split coloring) ──────────────────────────

_WRITE_VERBS: frozenset[str] = frozenset(
    {"Wrote", "Created", "Updated", "Saved", "Writing", "Moved", "Renamed", "Editing"}
)


def _fmt_path_rich(target: str, is_write: bool) -> str:
    """Color directory portion dim, filename bright."""
    display = _truncate_to_vault(target)
    try:
        p = Path(display)
        parent = str(p.parent)
        if parent != "." and parent != display:
            dir_safe  = _rich_escape(parent + "/")
            file_safe = _rich_escape(p.name)
            if is_write:
                return (
                    f"[dim green]{dir_safe}[/dim green]"
                    f"[bold green]{file_safe}[/bold green]"
                )
            return f"[dim cyan]{dir_safe}[/dim cyan][cyan]{file_safe}[/cyan]"
    except Exception:
        pass
    if is_write:
        return f"[green]{_rich_escape(display)}[/green]"
    return f"[dim cyan]{_rich_escape(display)}[/dim cyan]"


def _fmt_tool_use_rich(name: str, tool_input: dict) -> str:
    """Return full Rich markup for a tool-use event with dir/file path coloring."""
    verb   = _TOOL_VERB.get(name, name)
    target = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("pattern")
        or tool_input.get("query")
        or (str(tool_input.get("command", ""))[:70] if tool_input.get("command") else "")
        or ""
    )
    is_write    = verb in _WRITE_VERBS
    verb_markup = (
        f"[green]{_rich_escape(verb)}[/green]" if is_write
        else f"[dim cyan]{_rich_escape(verb)}[/dim cyan]"
    )
    if not target:
        return verb_markup
    return f"{verb_markup}  {_fmt_path_rich(target, is_write)}"


# ── Screen ─────────────────────────────────────────────────────────────────────

class IngestScreen(Screen):

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        # Shadow App-level nav bindings so they cannot fire mid-ingest.
        Binding("h", "noop", show=False),
        Binding("s", "noop", show=False),
        Binding("i", "noop", show=False),
        Binding("t", "noop", show=False),
    ]

    DEFAULT_CSS = """
    IngestScreen {
        align: center top;
        padding: 1 0;
    }

    #panel {
        width: 90;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 0;
    }

    #status {
        text-align: center;
        color: $text-muted;
        height: 1;
        margin-bottom: 0;
    }

    #thinking {
        height: 1;
        margin-bottom: 0;
        display: none;
    }

    #ingest-log {
        height: 20;
        border: round $panel;
        padding: 0 1;
        margin-bottom: 0;
    }

    #token-bar {
        height: 1;
        text-align: center;
        color: $text-muted;
        margin-top: 0;
        margin-bottom: 0;
    }

    #input-row {
        height: 3;
    }

    #user-input {
        width: 1fr;
    }

    #send-btn {
        width: 10;
        margin-left: 1;
    }

    #run-again-btn {
        width: 100%;
        margin-top: 1;
        display: none;
    }

    #hint {
        color: $text-muted;
        text-align: center;
        height: 1;
        margin-top: 0;
    }
    """

    def __init__(self, vault_root: Path) -> None:
        super().__init__()
        self._vault_root      = vault_root
        self._ingesting       = False
        self._proc: subprocess.Popen | None = None
        self._pending_tool_id: str | None   = None
        self._banner_shown    = False
        self._session         = 0   # incremented each time _begin() fires

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static("KOS Capture — Ingest", id="title")
            yield Static("Initialising…", id="status")
            yield LoadingIndicator(id="thinking")
            yield RichLog(id="ingest-log", markup=True, highlight=False, wrap=True)
            yield Static("", id="token-bar", markup=True)
            with Horizontal(id="input-row"):
                yield Input(placeholder="Reply to Claude…", id="user-input")
                yield Button("Send", id="send-btn")
            yield Button("Run /kos-ingest Again →", id="run-again-btn", variant="warning")
            yield Static("\\[Esc] back", id="hint")
        yield Footer()

    def on_show(self) -> None:
        if not self._ingesting:
            self._begin()

    def on_unmount(self) -> None:
        proc = self._proc
        if proc is not None:
            try:
                proc.stdin.close()
            except (OSError, AttributeError):
                pass
            if proc.poll() is None:
                try:
                    proc.terminate()
                except OSError:
                    pass

    # ── Actions ────────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        run_again_visible = self.query_one("#run-again-btn", Button).display
        if self._ingesting and not run_again_visible:
            self.app.notify("Ingest in progress — please wait.", severity="warning")
            return
        self.app.pop_screen()

    def action_noop(self) -> None:
        """Absorb shadowed App-level nav bindings — do nothing."""

    # ── User input ─────────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            self._send_user_input()
        elif event.button.id == "run-again-btn":
            self._begin()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "user-input":
            self._send_user_input()

    def _send_user_input(self) -> None:
        inp  = self.query_one("#user-input", Input)
        text = inp.value.strip()
        proc = self._proc
        if not text or proc is None or proc.stdin is None:
            return
        inp.value = ""
        self.query_one("#ingest-log", RichLog).write(
            f"[bold #60A5FA]You[/bold #60A5FA][bold yellow]:[/bold yellow] {_rich_escape(text)}"
        )
        try:
            if self._pending_tool_id:
                content = [{
                    "type":        "tool_result",
                    "tool_use_id": self._pending_tool_id,
                    "content":     [{"type": "text", "text": text}],
                }]
                self._pending_tool_id = None
                self.query_one("#user-input", Input).placeholder = "Reply to Claude…"
            else:
                content = [{"type": "text", "text": text}]
            msg = json.dumps({
                "type": "user",
                "message": {"role": "user", "content": content},
            }) + "\n"
            proc.stdin.write(msg)
            proc.stdin.flush()
            self._set_thinking(True)
            self.query_one("#status", Static).update("[yellow]Thinking…[/yellow]")
        except OSError:
            pass

    # ── State helpers ──────────────────────────────────────────────────────────

    def _lock_input(self) -> None:
        self.query_one("#user-input", Input).disabled = True
        self.query_one("#send-btn",   Button).disabled = True

    def _unlock_input(self) -> None:
        self.query_one("#user-input", Input).disabled = False
        self.query_one("#send-btn",   Button).disabled = False

    def _log_line(self, line: str) -> None:
        self.query_one("#ingest-log", RichLog).write(line)

    def _log_error(self, msg: str) -> None:
        self.query_one("#ingest-log", RichLog).write(f"[red]{_rich_escape(msg)}[/red]")
        self.query_one("#status",     Static).update("[red]Error.[/red]")

    def _log_table(self, rows: list[str]) -> None:
        """Render a buffered Markdown table to the log; falls back to plain lines."""
        log   = self.query_one("#ingest-log", RichLog)
        table = _render_md_table(rows)
        if table is not None:
            log.write(table)
        else:
            for row in rows:
                log.write(_fmt_ingest_line(row))

    def _show_banner(self, version: str, model: str, plan: str) -> None:
        if self._banner_shown:
            return
        self._banner_shown = True
        vault   = str(self._vault_root).replace(str(Path.home()), "~")
        ver_str = f"v{_rich_escape(version)}" if version else ""
        meta    = _rich_escape(model) + (" · " + _rich_escape(plan) if plan else "")
        log = self.query_one("#ingest-log", RichLog)
        log.write(f"[bold #D97757] ▐▛███▜▌[/bold #D97757]   [#F4A261]Claude Code {ver_str}[/#F4A261]")
        log.write(f"[bold #D97757]▝▜█████▛▘[/bold #D97757]  [#F4A261]{meta}[/#F4A261]")
        log.write(f"[bold #D97757]  ▘▘ ▝▝[/bold #D97757]    [#F4A261]{_rich_escape(vault)}[/#F4A261]")
        log.write("")

    def _update_token_bar(self, usage: dict, cost_usd: float | None) -> None:
        inp_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        cache_r = usage.get("cache_read_input_tokens", 0)
        parts: list[str] = [
            f"[dim]In:[/dim] [white]{inp_tok:,}[/white]",
            f"[dim]Out:[/dim] [white]{out_tok:,}[/white]",
        ]
        if cache_r:
            parts.append(f"[dim]Cache:[/dim] [white]{cache_r:,}[/white]")
        if cost_usd is not None:
            parts.append(
                f"[dim]Cost:[/dim] [bold #00C853]${cost_usd:.4f}[/bold #00C853]"
            )
        stats = "  [dim]·[/dim]  ".join(parts)
        self.query_one("#token-bar", Static).update(
            f"[bold #FF8C00]Token Bar[/bold #FF8C00]  {stats}"
        )

    def _set_thinking(self, thinking: bool) -> None:
        self.query_one("#thinking", LoadingIndicator).display = thinking

    def _set_status_text(self, markup: str) -> None:
        self.query_one("#status", Static).update(markup)

    def _show_question(self, question: str, options: list[dict], tool_id: str) -> None:
        self._pending_tool_id = tool_id
        self._set_thinking(False)
        log = self.query_one("#ingest-log", RichLog)
        log.write("")
        log.write(f"[bold #FF6B35]{_rich_escape(question)}[/bold #FF6B35]")
        for i, opt in enumerate(options, 1):
            label      = _rich_escape(opt.get("label", ""))
            desc       = opt.get("description", "")
            num_markup = f"[bold #C084FC]{i}[/bold #C084FC][dim].[/dim]"
            if desc:
                log.write(f"  {num_markup} {label} — {_rich_escape(desc)}")
            else:
                log.write(f"  {num_markup} {label}")
        log.write("")
        inp = self.query_one("#user-input", Input)
        inp.placeholder = "Type option label or number…"
        inp.focus()
        self.query_one("#status", Static).update(
            "[bold #FF6B35]Awaiting your reply…[/bold #FF6B35]"
        )

    def _on_turn_complete(self, usage: dict | None = None, cost_usd: float | None = None) -> None:
        """Claude finished one turn — stay live, focus input so user can reply."""
        self._pending_tool_id = None
        self._set_thinking(False)
        if usage:
            self._update_token_bar(usage, cost_usd)
        self.query_one("#run-again-btn", Button).display = True
        self.query_one("#status", Static).update("[dim]Awaiting reply…[/dim]")
        inp = self.query_one("#user-input", Input)
        inp.placeholder = "Reply to Claude…"
        inp.focus()

    def _on_done(self) -> None:
        self._ingesting       = False
        self._proc            = None
        self._pending_tool_id = None
        self._set_thinking(False)
        self._lock_input()
        self.query_one("#run-again-btn", Button).display = True
        self.query_one("#status", Static).update("[green]Ingest complete.[/green]")
        self.query_one("#hint",   Static).update("\\[Esc] back to Results")
        self.app.notify("Ingest complete.", severity="information")

    # ── Entry point ────────────────────────────────────────────────────────────

    def _begin(self) -> None:
        global _vault_root_display
        _vault_root_display = self._vault_root
        claude_bin = shutil.which("claude")
        if not claude_bin:
            self._log_error(
                "claude not found on PATH — install Claude Code and ensure it is on PATH"
            )
            return

        # Kill any running process from a previous session before restarting.
        old_proc, self._proc = self._proc, None
        if old_proc is not None and old_proc.poll() is None:
            try:
                old_proc.stdin.close()
            except (OSError, AttributeError):
                pass
            try:
                old_proc.terminate()
            except OSError:
                pass

        self._session        += 1
        self._ingesting       = True
        self._pending_tool_id = None
        self._banner_shown    = False
        self.query_one("#ingest-log",    RichLog).clear()
        self.query_one("#token-bar",     Static).update(
            f"[bold #FF8C00]Token Bar[/bold #FF8C00]  [dim]counting…[/dim]"
        )
        self.query_one("#run-again-btn", Button).display = False
        self.query_one("#status",        Static).update("[yellow]Starting…[/yellow]")
        self._unlock_input()
        self._set_thinking(True)
        self._run_ingest(claude_bin, self._session)

    # ── Worker ─────────────────────────────────────────────────────────────────

    @work(thread=True)
    def _run_ingest(self, claude_bin: str, session: int) -> None:
        try:
            proc = subprocess.Popen(
                [
                    claude_bin,
                    "--input-format",  "stream-json",
                    "--output-format", "stream-json",
                    "--verbose",
                    "--permission-mode", "acceptEdits",
                    "--disallowed-tools", "AskUserQuestion",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self._vault_root),
                text=True,
                bufsize=1,
            )
            self._proc = proc
        except Exception as exc:
            self.app.call_from_thread(self._log_error, f"Failed to start claude: {exc}")
            self.app.call_from_thread(self._on_done)
            return

        # Send initial prompt as a stream-json user message
        try:
            assert proc.stdin is not None
            proc.stdin.write(
                json.dumps({
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "/kos-ingest"}],
                    },
                }) + "\n"
            )
            proc.stdin.flush()
            self.app.call_from_thread(
                self._set_status_text, "[yellow]Thinking…[/yellow]"
            )
        except OSError as exc:
            self.app.call_from_thread(self._log_error, f"Failed to send command: {exc}")
            self.app.call_from_thread(self._on_done)
            return

        assert proc.stdout is not None
        table_buffer: list[str] = []

        def _flush_table_buf() -> None:
            if table_buffer:
                buf = table_buffer.copy()
                table_buffer.clear()
                self.app.call_from_thread(self._log_table, buf)

        try:
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    clean = _strip_ansi(line)
                    if clean.strip():
                        self.app.call_from_thread(self._log_line, _fmt_ingest_line(clean))
                    continue

                ev_type = event.get("type", "")

                if ev_type == "system" and event.get("subtype") == "init":
                    model   = _friendly_model(event.get("model", ""))
                    plan    = event.get("plan", "")
                    version = event.get("version", "")
                    if not version:
                        try:
                            version = Path(os.path.realpath(
                                shutil.which("claude") or ""
                            )).name
                        except Exception:
                            version = ""
                    self.app.call_from_thread(
                        self._show_banner, version, model, plan
                    )

                elif ev_type == "result":
                    if event.get("is_error"):
                        self.app.call_from_thread(
                            self._log_error,
                            _strip_ansi(event.get("result", "Ingest failed.")),
                        )
                        break
                    usage    = event.get("usage") or {}
                    cost_usd = event.get("total_cost_usd") or event.get("cost_usd")
                    self.app.call_from_thread(self._on_turn_complete, usage, cost_usd)

                elif ev_type == "assistant":
                    for block in event.get("message", {}).get("content", []):
                        btype = block.get("type", "")
                        if btype == "text":
                            self.app.call_from_thread(
                                self._set_status_text, "[#5BC8C8]Answering…[/#5BC8C8]"
                            )
                            for text_line in block.get("text", "").splitlines():
                                clean = _strip_ansi(text_line).strip()
                                if not clean:
                                    _flush_table_buf()
                                    continue
                                if clean.startswith("|"):
                                    table_buffer.append(clean)
                                else:
                                    _flush_table_buf()
                                    self.app.call_from_thread(
                                        self._log_line, _fmt_ingest_line(clean)
                                    )
                            _flush_table_buf()
                        elif btype == "tool_use":
                            _flush_table_buf()
                            name     = block.get("name", "")
                            tool_inp = block.get("input", {})
                            tool_id  = block.get("id", "")
                            if name == "AskUserQuestion":
                                questions = tool_inp.get("questions", [])
                                if questions:
                                    q = questions[0]
                                    self.app.call_from_thread(
                                        self._show_question,
                                        q.get("question", ""),
                                        q.get("options", []),
                                        tool_id,
                                    )
                            else:
                                verb = _TOOL_VERB.get(name, "Running")
                                self.app.call_from_thread(
                                    self._set_status_text,
                                    f"[dim cyan]{verb}…[/dim cyan]",
                                )
                                self.app.call_from_thread(
                                    self._log_line, _fmt_tool_use_rich(name, tool_inp)
                                )

            _flush_table_buf()  # flush any table at stream end

        finally:
            try:
                proc.stdin.close()
            except (OSError, AttributeError):
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait()
            try:
                if self._session == session:
                    self.app.call_from_thread(self._on_done)
            except Exception:
                pass
