"""
screens/inbox.py

Inbox screen — lists PDFs in the configured Proton Drive sync folder.

Flat scan of proton_drive: only PDFs directly in that directory, sorted
newest-first by modification time. Selecting a file pushes WizardScreen
with the file path. Refresh re-scans without leaving the screen.

Escape returns to Home. Config-missing state shows an error instead of
crashing. Empty folder shows a friendly prompt rather than a blank list.
"""

from __future__ import annotations

from pathlib import Path

import core.config as config
from screens.wizard import WizardScreen
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Label, ListItem, ListView, Static


def _format_size(n: int) -> str:
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f} MB"
    if n >= 1_024:
        return f"{n / 1_024:.1f} KB"
    return f"{n} B"


def _scan_pdfs(folder: Path) -> list[Path]:
    """Return PDFs directly in folder, newest-first by mtime."""
    if not folder.exists():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def _item_label(pdf: Path) -> str:
    stat = pdf.stat()
    size = _format_size(stat.st_size)
    from datetime import datetime
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
    name = pdf.name
    return f"{name:<40}  {size:>8}  {mtime}"


class InboxScreen(Screen):

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("r", "refresh", "Refresh", show=False),
    ]

    DEFAULT_CSS = """
    InboxScreen {
        align: center middle;
    }

    #panel {
        width: 80;
        height: auto;
        max-height: 36;
        border: round $primary;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #scan-path {
        color: $text-muted;
        height: 1;
        padding: 0;
        margin-bottom: 1;
    }

    #message {
        text-align: center;
        height: 1;
        padding: 0;
        margin-bottom: 1;
    }

    #file-list {
        height: auto;
        max-height: 20;
        background: transparent;
        border: round $panel;
        padding: 0 1;
        margin-bottom: 1;
    }

    #file-list > ListItem {
        background: transparent;
        height: 1;
        padding: 0;
    }

    #file-list > ListItem.--highlight {
        background: $primary 20%;
        color: $primary;
    }

    #file-list > ListItem > Label {
        width: 100%;
    }

    #hint {
        text-align: center;
        color: $text-muted;
        height: 1;
        padding: 0;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._pdfs: list[Path] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static("PDF Inbox", id="title")
            yield Static("", id="scan-path")
            yield Static("", id="message")
            yield ListView(id="file-list")
            yield Static("Enter to process  ·  [r] refresh  ·  [Esc] back", id="hint")
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    # ── Bindings ───────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.app.switch_screen("home")

    def action_refresh(self) -> None:
        self._load()

    # ── List selection ─────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one("#file-list", ListView).index
        if idx is not None and 0 <= idx < len(self._pdfs):
            self.app.push_screen(WizardScreen(self._pdfs[idx]))

    # ── Load / render ──────────────────────────────────────────────────────

    def _load(self) -> None:
        if not config.exists():
            self.query_one("#scan-path", Static).update("")
            self.query_one("#message", Static).update(
                "[red]No config found — run Setup first.[/red]"
            )
            self.query_one("#file-list", ListView).clear()
            self._pdfs = []
            return

        try:
            cfg = config.load()
        except Exception as exc:
            self.query_one("#message", Static).update(
                f"[red]Config error: {exc}[/red]"
            )
            return

        folder = cfg.proton_drive
        self.query_one("#scan-path", Static).update(
            f"  Scanning: [dim]{folder}[/dim]"
        )

        self._pdfs = _scan_pdfs(folder)
        file_list = self.query_one("#file-list", ListView)
        file_list.clear()

        if not self._pdfs:
            self.query_one("#message", Static).update(
                "[dim]No PDFs found — sync from Proton Drive first.[/dim]"
            )
            return

        self.query_one("#message", Static).update(
            f"[green]{len(self._pdfs)} PDF{'s' if len(self._pdfs) != 1 else ''} ready to process[/green]"
        )

        for pdf in self._pdfs:
            file_list.append(ListItem(Label(_item_label(pdf))))
