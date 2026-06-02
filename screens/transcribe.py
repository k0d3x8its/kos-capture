"""
screens/transcribe.py

Transcription screen — two-step flow for local audio and remote sources.

Steps:
  1. source  — choose Proton Meet / YouTube / Podcast from a ListView
  2. input   — enter file path or URL; optional custom title field;
               Begin Transcription button launches the worker
  3. running — live status log while worker runs (Escape blocked)

Title field behaviour:
    Blank → auto-derived: filename stem for local files, yt-dlp title for URLs.
    Filled → used as-is for the .md heading and output filename.

Podcast source handling:
    URL (http/https) → yt-dlp downloads audio → faster-whisper.
    Local path       → passed directly to faster-whisper (MP3, M4A, WAV, etc.).

Meetings source: any local audio/video file ffmpeg handles — not restricted to MP4.

On success: output .md path appended to app.session_results; screen switches
to Ready. On error: log shows the message, Escape re-enabled to retry.
Escape on step 1 → Home. Escape on step 2 → back to step 1.
"""

from __future__ import annotations

from pathlib import Path

import core.config as config
import core.transcribe as transcribe
from screens.ready import ReadyScreen
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, ContentSwitcher, Footer, Input, Label, ListItem, ListView, ProgressBar, RichLog, Static


_SOURCES: list[tuple[str, str]] = [
    ("Proton Meet  (local audio/video)", "meetings"),
    ("YouTube  (URL)", "youtube"),
    ("Podcast  (URL or local file)", "podcasts"),
]

_STEP_LABELS: dict[str, str] = {
    "step-source":  "Step 1 of 2 — Choose source type",
    "step-input":   "Step 2 of 2 — Enter source",
    "step-running": "",
}

_SOURCE_PLACEHOLDERS: dict[str, str] = {
    "meetings": "/path/to/Proton Meet recording.mp4",
    "youtube":  "https://www.youtube.com/watch?v=…",
    "podcasts":  "https://example.com/episode.mp3  or  /path/to/episode.mp3",
}

_TITLE_PLACEHOLDERS: dict[str, str] = {
    "meetings": "Auto — uses filename stem",
    "youtube":  "Auto — uses video title from yt-dlp",
    "podcasts":  "Auto — filename stem (local) or episode title from yt-dlp (URL)",
}


class TranscribeScreen(Screen):

    BINDINGS = [Binding("escape", "go_back", "Back")]

    DEFAULT_CSS = """
    TranscribeScreen {
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
        margin-bottom: 0;
    }

    #step-label {
        color: $primary;
        text-style: bold;
        height: 1;
        margin-top: 1;
        margin-bottom: 1;
    }

    #errors {
        color: $error;
        height: auto;
        margin-bottom: 1;
    }

    ContentSwitcher {
        height: auto;
        max-height: 18;
    }

    .choice-list {
        height: auto;
        max-height: 6;
        border: round $panel;
        background: transparent;
        padding: 0 1;
        margin-bottom: 1;
    }

    .choice-list > ListItem {
        background: transparent;
        height: 1;
        padding: 0;
    }

    #panel .choice-list > ListItem.-highlight {
        background: transparent;
    }

    .choice-list > ListItem > Label {
        width: 100%;
        color: $text-muted;
    }

    #panel .choice-list > ListItem.-highlight > Label {
        color: #00ff00;
        text-style: bold;
    }

    .input-label {
        color: $text-muted;
        height: 1;
        margin-top: 1;
    }

    #source-input {
        margin-bottom: 0;
    }

    #title-input {
        margin-bottom: 1;
    }

    #begin-btn {
        width: 100%;
        margin-top: 1;
    }

    #run-source {
        color: $text-muted;
        height: 1;
        margin-bottom: 0;
    }

    #run-log {
        height: auto;
        max-height: 6;
        border: round $panel;
        padding: 0 1;
        margin-top: 1;
        margin-bottom: 0;
    }

    .progress-label {
        color: $text-muted;
        height: 1;
        margin-top: 1;
        margin-bottom: 0;
    }

    #run-dl-progress, #run-progress {
        width: 100%;
        margin-top: 0;
        margin-bottom: 0;
    }

    #run-status {
        color: $text-muted;
        text-align: center;
        height: 1;
        margin-top: 1;
        margin-bottom: 0;
    }

    #retry-btn {
        width: 100%;
        margin-top: 1;
        display: none;
    }

    #hint {
        color: $text-muted;
        text-align: center;
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._source_type = ""
        self._step = "step-source"
        self._transcribing = False

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static("KOS Capture — Transcribe", id="title")
            yield Static("", id="step-label")
            yield Static("", id="errors")
            with ContentSwitcher(initial="step-source", id="switcher"):
                with Vertical(id="step-source"):
                    yield ListView(
                        *[ListItem(Label(label)) for label, _ in _SOURCES],
                        id="source-list",
                        classes="choice-list",
                    )
                with Vertical(id="step-input"):
                    yield Label("Source", classes="input-label")
                    yield Input(placeholder="", id="source-input")
                    yield Label("Title  (optional)", classes="input-label")
                    yield Input(placeholder="", id="title-input")
                    yield Button("Begin Transcription →", id="begin-btn", variant="primary")
                with Vertical(id="step-running"):
                    yield Static("", id="run-source")
                    yield RichLog(id="run-log", markup=True, highlight=False, wrap=True)
                    yield Static("Download", id="dl-label", classes="progress-label")
                    yield ProgressBar(total=100, show_eta=False, id="run-dl-progress")
                    yield Static("Transcription", id="tr-label", classes="progress-label")
                    yield ProgressBar(total=100, show_eta=False, id="run-progress")
                    yield Static("", id="run-status")
                    yield Button("Try Again", id="retry-btn", variant="primary")
            yield Static("\\[Enter] select  ·  \\[Esc] back", id="hint")
        yield Footer()

    def on_mount(self) -> None:
        self._update_step_label()
        self._focus_step()

    def on_show(self) -> None:
        if not self._transcribing:
            self.call_after_refresh(self._reset_to_source)

    def _reset_to_source(self) -> None:
        self._go_to("step-source")
        self.query_one("#errors", Static).update("")

    # ── Step helpers ────────────────────────────────────────────────────────

    def _update_step_label(self) -> None:
        self.query_one("#step-label", Static).update(_STEP_LABELS[self._step])

    def _go_to(self, step: str) -> None:
        self._step = step
        self._update_step_label()
        self.query_one("#errors", Static).update("")
        self.query_one(ContentSwitcher).current = step
        _hints = {
            "step-source": "\\[Enter] select  ·  \\[Esc] back",
            "step-input":  "\\[Ctrl+Shift+V] paste  ·  \\[Enter] next field  ·  \\[Esc] back",
        }
        if step in _hints:
            self.query_one("#hint", Static).update(_hints[step])
        self._focus_step()

    def _focus_step(self) -> None:
        targets: dict[str, str] = {
            "step-source":  "#source-list",
            "step-input":   "#source-input",
            "step-running": "#run-log",
        }
        selector = targets.get(self._step)
        if selector:
            try:
                widget = self.query_one(selector)
                widget.focus()
                if hasattr(widget, "index"):
                    def _reset(w=widget) -> None:
                        w.index = None
                        w.index = 0
                    self.call_after_refresh(_reset)
            except Exception:
                pass

    # ── Navigation ──────────────────────────────────────────────────────────

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            self.action_go_back()
        elif event.key == "t" and self._step == "step-running" and not self._transcribing:
            # App-level "t" binding is a no-op when already on TranscribeScreen;
            # intercept here to give the user a direct retry path after an error.
            event.stop()
            self._reset_to_source()

    def action_go_back(self) -> None:
        if self._transcribing:
            self.app.notify("Transcription in progress — please wait.", severity="warning")
            return
        if self._step == "step-source":
            self.app.switch_screen("home")
        else:
            self._go_to("step-source")

    # ── Source selection ────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "source-list":
            return
        idx = event.list_view.index
        if idx is None or idx >= len(_SOURCES):
            return
        _, source_type = _SOURCES[idx]
        self._source_type = source_type
        self.query_one("#source-input", Input).placeholder = _SOURCE_PLACEHOLDERS[source_type]
        self.query_one("#source-input", Input).value = ""
        self.query_one("#title-input", Input).placeholder = _TITLE_PLACEHOLDERS[source_type]
        self.query_one("#title-input", Input).value = ""
        self._go_to("step-input")

    # ── Input handling ──────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "source-input":
            self.query_one("#title-input", Input).focus()
        elif event.input.id == "title-input":
            self._begin()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "begin-btn":
            self._begin()
        elif event.button.id == "retry-btn":
            self._reset_to_source()

    # ── Validation + worker launch ──────────────────────────────────────────

    def _begin(self) -> None:
        errors = self.query_one("#errors", Static)
        raw = self.query_one("#source-input", Input).value.strip()
        custom_title = self.query_one("#title-input", Input).value.strip() or None

        if not raw:
            errors.update("[red]Source is required.[/red]")
            return

        # Local-file validation — meetings always local; podcasts when not a URL
        needs_local_check = self._source_type == "meetings" or (
            self._source_type == "podcasts" and not transcribe._is_url(raw)
        )
        if needs_local_check:
            p = Path(raw).expanduser()
            if not p.exists():
                errors.update(f"[red]File not found: {raw}[/red]")
                return

        if not config.exists():
            errors.update("[red]No config — run Setup first.[/red]")
            return

        try:
            cfg = config.load()
        except Exception as exc:
            errors.update(f"[red]Config error: {exc}[/red]")
            return

        self._transcribing = True
        self.query_one("#retry-btn").display = False
        self._go_to("step-running")

        source_label = f"[bold]{self._source_type.capitalize()}[/bold]  {raw}"
        if custom_title:
            source_label += f"  ·  [bold]Title:[/bold] {custom_title}"
        self.query_one("#run-source", Static).update(source_label)
        self.query_one("#run-status", Static).update("")
        self.query_one("#run-progress", ProgressBar).update(progress=0)

        is_url = self._source_type == "youtube" or (
            self._source_type == "podcasts" and transcribe._is_url(raw)
        )
        self.query_one("#dl-label").display = is_url
        self.query_one("#run-dl-progress").display = is_url
        self.query_one("#run-dl-progress", ProgressBar).update(progress=0)

        log = self.query_one("#run-log", RichLog)
        log.clear()
        self.query_one("#hint", Static).update(
            "[yellow]Downloading — please wait[/yellow]" if is_url
            else "[yellow]Transcription running — please wait[/yellow]"
        )
        self.app.notify("Transcription started…", severity="information")

        transcript_dir = cfg.vault_root / "raw" / "transcripts" / self._source_type
        self._run_transcription(self._source_type, raw, transcript_dir, custom_title)

    @work(thread=True)
    def _run_transcription(
        self,
        source_type: str,
        source: str,
        transcript_dir: Path,
        title: str | None,
    ) -> None:
        log = self.query_one("#run-log", RichLog)

        def _set_pct(pct: float) -> None:
            self.query_one("#run-progress", ProgressBar).update(progress=pct * 100)

        def _set_dl_pct(pct: float) -> None:
            self.query_one("#run-dl-progress", ProgressBar).update(progress=pct * 100)

        def _on_transcribing() -> None:
            self.query_one("#hint", Static).update(
                "[yellow]Transcription running — please wait[/yellow]"
            )

        try:
            src: Path | str = (
                Path(source).expanduser() if not transcribe._is_url(source) else source
            )
            out_path = transcribe.run(
                source_type=source_type,
                source=src,
                transcript_dir=transcript_dir,
                title=title,
                on_progress=lambda msg: self.app.call_from_thread(log.write, msg),
                on_pct=lambda pct: self.app.call_from_thread(_set_pct, pct),
                on_dl_pct=lambda pct: self.app.call_from_thread(_set_dl_pct, pct),
                on_transcribing=lambda: self.app.call_from_thread(_on_transcribing),
            )
            self.app.call_from_thread(self._on_transcription_done, out_path)
        except Exception as exc:
            self.app.call_from_thread(self._on_transcription_error, str(exc))

    def _on_transcription_done(self, out_path: Path) -> None:
        self._transcribing = False
        self.app.session_results.append(out_path)
        self.app.notify(f"Transcript → {out_path.name}", severity="information")
        self._reset_to_source()
        self.app.switch_screen(ReadyScreen())

    def _on_transcription_error(self, message: str) -> None:
        self._transcribing = False
        log = self.query_one("#run-log", RichLog)
        log.write(f"[red]Error: {message}[/red]")
        self.query_one("#run-status", Static).update("[red]Transcription failed.[/red]")
        self.query_one("#retry-btn").display = True
        self.query_one("#hint", Static).update("\\[Esc] back  ·  \\[t] try again")
        self.app.notify("Transcription failed", severity="error")
