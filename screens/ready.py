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

    def on_show(self) -> None:
        self._populate_log()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "done-btn":
            self.app.switch_screen("home")

    def action_go_back(self) -> None:
        self.app.switch_screen("home")
