"""
screens/ready.py

Session summary — shown after the user finishes processing Inbox files.

File entries are formatted like the sync screen log: filename padded to a
fixed column, double-line arrow, then collection/volume destination.
Paths are checked for existence — missing files are dimmed with a ✗ marker.

Navigation:
  - Escape → back to Inbox
  - Done   → back to Home

session_results persists across screens and only clears on app restart.
That keeps "View Summary" reachable from Inbox throughout the run, so
users never lose visibility by hitting Done by accident.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, RichLog, Static


_PATH_COL = 31


def _fmt_result(path: Path) -> str:
    name = path.name
    parts = path.parts
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
        max-height: 12;
        border: round $panel;
        padding: 0 1;
        margin-bottom: 1;
    }

    #ingest-box {
        border: round $panel;
        padding: 0 1;
        height: auto;
        margin-bottom: 1;
    }

    #ingest-cmd {
        color: #00ff00;
        text-style: bold;
    }

    #ingest-note {
        color: $text-muted;
        height: 1;
    }

    #done-btn {
        width: 100%;
        margin-top: 1;
        background: #00ff00;
        color: #000000;
    }

    #done-btn:hover {
        background: #33ff33;
        color: #000000;
    }
    """

    def compose(self) -> ComposeResult:
        count = len(self.app.session_results)
        noun = "File" if count == 1 else "Files"

        with Vertical(id="panel"):
            yield Static(f"Session Complete — {count} {noun} Ready", id="title")
            yield RichLog(id="file-log", markup=True, highlight=False, wrap=False)

            with Vertical(id="ingest-box"):
                yield Static("/kos-ingest", id="ingest-cmd")
                yield Static(
                    "Run in your agent to process the files above.",
                    id="ingest-note",
                )

            yield Button("Done →", id="done-btn", variant="primary")

        yield Footer()

    def _populate_log(self) -> None:
        log = self.query_one("#file-log", RichLog)
        log.clear()
        count = len(self.app.session_results)
        noun = "File" if count == 1 else "Files"
        self.query_one("#title", Static).update(
            f"Session Complete — {count} {noun} Ready"
        )
        for path in self.app.session_results:
            line = _fmt_result(path)
            if path.exists():
                log.write(line)
            else:
                log.write(f"[dim]{line}  ✗[/dim]")

    def on_mount(self) -> None:
        self._populate_log()

    def on_show(self) -> None:
        self._populate_log()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "done-btn":
            self.app.switch_screen("home")

    def action_go_back(self) -> None:
        self.app.switch_screen("inbox")
