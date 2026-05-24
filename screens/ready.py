"""
screens/ready.py

Session summary — shown after the user finishes processing Inbox files.

Results are grouped by source category: Field Logs / Field Research /
Field Studies (PDFs), then Meetings / YouTube / Podcasts (transcripts).
Each group shows a bold header followed by indented file entries.
Paths are checked for existence — missing files are dimmed with a ✗ marker.

Navigation:
  - Escape → back to Home
  - Done   → back to Home

session_results persists across screens and only clears on app restart.
That keeps "View Results" reachable throughout the run.
"""

from __future__ import annotations

from pathlib import Path

import core.config as config
from screens.ingest import IngestScreen
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, RichLog, Static


_PATH_COL = 31

_CATEGORY_ORDER: list[tuple[str, str]] = [
    ("Field-Logs",     "Field Logs"),
    ("Field-Research", "Field Research"),
    ("Field-Studies",  "Field Studies"),
    ("meetings",       "Meetings"),
    ("youtube",        "YouTube"),
    ("podcasts",       "Podcasts"),
]

_KNOWN_CATEGORIES: frozenset[str] = frozenset(k for k, _ in _CATEGORY_ORDER)


def _categorize(path: Path) -> str:
    parts = path.parts
    if len(parts) >= 3 and parts[-3] == "transcripts":
        key = parts[-2]           # youtube / podcasts / meetings
    elif len(parts) >= 3:
        key = parts[-3]           # Field-Logs / Field-Research / Field-Studies
    else:
        return "other"
    return key if key in _KNOWN_CATEGORIES else "other"


def _fmt_entry(path: Path, category: str) -> str:
    name = path.name
    parts = path.parts
    if category in ("Field-Logs", "Field-Research", "Field-Studies"):
        dest = parts[-2] if len(parts) >= 2 else str(path.parent)
    else:
        dest = f"{parts[-3]}/{parts[-2]}" if len(parts) >= 3 else str(path.parent)
    p = min(len(name), _PATH_COL)
    pad = _PATH_COL - p
    return f"{name[:p]}{' ' * (pad + 1)}⟹  {dest}"


class ReadyScreen(Screen):

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    DEFAULT_CSS = """
    ReadyScreen {
        align: center top;
        padding: 1 0;
    }

    #panel {
        width: 72;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #file-log {
        height: auto;
        max-height: 15;
        border: round $panel;
        padding: 0 1;
        margin-bottom: 1;
    }

    #ingest-btn {
        width: 100%;
        margin-bottom: 1;
    }

    #more-files-btn {
        width: 100%;
        margin-bottom: 1;
    }

    #transcribe-btn {
        width: 100%;
        margin-bottom: 1;
    }

    #done-btn {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        count = len(self.app.session_results)
        noun = "File" if count == 1 else "Files"

        with Vertical(id="panel"):
            yield Static(f"Session Complete — {count} {noun} Ready", id="title")
            yield RichLog(id="file-log", markup=True, highlight=False, wrap=False)

            yield Button("Ingest Now →",          id="ingest-btn",    variant="success")
            yield Button("More Files from Inbox →", id="more-files-btn", variant="primary")
            yield Button("Transcribe More →",       id="transcribe-btn", variant="primary")
            yield Button("Done →",                  id="done-btn",       variant="default")

        yield Footer()

    def _populate_log(self) -> None:
        log = self.query_one("#file-log", RichLog)
        log.clear()
        count = len(self.app.session_results)
        noun = "File" if count == 1 else "Files"
        self.query_one("#title", Static).update(
            f"Session Complete — {count} {noun} Ready"
        )

        if not self.app.session_results:
            return

        groups: dict[str, list[Path]] = {}
        for path in self.app.session_results:
            cat = _categorize(path)
            groups.setdefault(cat, []).append(path)

        first = True
        for key, label in _CATEGORY_ORDER:
            if key not in groups:
                continue
            if not first:
                log.write("")
            first = False
            log.write(f"[bold #00ff41]{label}[/bold #00ff41]")
            for path in groups[key]:
                entry = _fmt_entry(path, key)
                if path.exists():
                    log.write(f"  {entry}")
                else:
                    log.write(f"  [dim]{entry}  ✗[/dim]")

        if "other" in groups:
            if not first:
                log.write("")
            log.write("[bold]Other[/bold]")
            for path in groups["other"]:
                entry = _fmt_entry(path, "other")
                if path.exists():
                    log.write(f"  {entry}")
                else:
                    log.write(f"  [dim]{entry}  ✗[/dim]")

    def on_mount(self) -> None:
        self._populate_log()
        self._update_ingest_btn()

    def on_show(self) -> None:
        self._populate_log()
        self._update_ingest_btn()

    def _update_ingest_btn(self) -> None:
        """Enable Ingest Now only when config is valid and vault_root exists."""
        btn = self.query_one("#ingest-btn", Button)
        if not config.exists():
            btn.disabled = True
            btn.tooltip  = "Run Setup first"
            return
        try:
            cfg = config.load()
            if cfg.vault_root.exists():
                btn.disabled = False
                btn.tooltip  = None
            else:
                btn.disabled = True
                btn.tooltip  = "Vault root not found"
        except Exception:
            btn.disabled = True
            btn.tooltip  = "Config error — run Setup"

    def _start_ingest(self) -> None:
        try:
            cfg = config.load()
        except Exception as exc:
            self.app.notify(f"Config error: {exc}", severity="error")
            return
        self.app.push_screen(IngestScreen(cfg.vault_root))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ingest-btn":
            self._start_ingest()
        elif event.button.id == "more-files-btn":
            self.app.switch_screen("inbox")
        elif event.button.id == "transcribe-btn":
            self.app.switch_screen("transcribe")
        elif event.button.id == "done-btn":
            self.app.switch_screen("home")

    def action_go_back(self) -> None:
        self.app.switch_screen("home")
