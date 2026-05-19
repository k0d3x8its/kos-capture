"""
screens/home.py

Home screen — first screen seen after setup completes.

Shows:
  - ASCII art title via pyfiglet (ansi_shadow + calvin_s)
  - Centered navigation menu with arrow key selection or letter shortcuts
  - Compact system status panel below the menu

Navigation: Up/Down to move, Enter to select — or press the letter key directly.
ctrl+q to quit (app-level binding).
"""

import pyfiglet

import core.config as config
import core.rclone as rclone
from screens.modal import ErrorModal
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static


def _status_line(ok: bool, label: str) -> str:
    """Format a coloured ✓/✗ status line using Rich markup."""
    icon = "[bold #00ff00]✓[/bold #00ff00]" if ok else "[bold red]✗[/bold red]"
    return f"  {icon}  {label}"


# (rich_label, item_id) — all items padded to 16 chars so text-align: center works uniformly
# \[ escapes to a literal [ in Rich markup
_NAV_ITEMS = [
    ("\\[s]---------Sync",   "nav-sync"),
    ("\\[i]--------Inbox",   "nav-inbox"),
    ("\\[t]---Transcribe",   "nav-transcribe"),
    ("\\[c]-------Config",   "nav-config"),
    ("\\[r]------Refresh",   "nav-refresh"),
    ("\\[^q]--------Quit",   "nav-quit"),
]


class HomeScreen(Screen):

    BINDINGS = [
        Binding("s", "go_sync",        show=False),
        Binding("i", "go_inbox",       show=False),
        Binding("t", "go_transcribe",  show=False),
        Binding("c", "go_config",      show=False),
        Binding("r", "refresh_status", show=False),
    ]

    DEFAULT_CSS = """
    HomeScreen {
        align: center middle;
    }

    #container {
        width: auto;
        height: auto;
        align: center middle;
    }

    #banner {
        text-align: center;
        color: $primary;
        width: 100%;
        padding: 0;
        margin-top: 1;
        margin-bottom: 0;
    }

    #separator-top {
        text-align: center;
        color: $primary;
        height: 1;
        padding: 0;
        margin: 0;
    }

    #tagline {
        text-align: center;
        color: $text-muted;
        height: 1;
        padding: 0;
        margin: 0;
    }

    #separator-bottom {
        text-align: center;
        color: $primary;
        height: 1;
        padding: 0;
        margin-bottom: 1;
    }

    #nav-panel {
        width: 40;
        height: auto;
        border: double $primary;
        padding: 1 1;
        margin-bottom: 1;
    }

    #nav-title {
        text-style: bold;
        text-align: center;
        height: 1;
        padding: 0;
        margin-bottom: 0;
    }

    #nav-separator {
        text-align: center;
        color: $primary;
        height: 1;
        padding: 0;
        margin-bottom: 1;
    }

    #nav-list {
        height: auto;
        width: 100%;
        background: transparent;
        border: none;
        padding: 0;
        margin: 0;
    }

    #nav-list > ListItem {
        background: transparent;
        height: 1;
        padding: 0;
        width: 100%;
    }

    #nav-list > ListItem > Label {
        width: 100%;
        text-align: center;
        color: $text-muted;
    }

    #nav-list > ListItem.-highlight {
        background: transparent;
    }

    #nav-list > ListItem.-highlight > Label {
        color: #00ff00;
        text-style: bold;
    }

    #status-panel {
        width: 52;
        height: auto;
        border: round $panel;
        padding: 0 2;
        margin-bottom: 1;
    }

    #status-title {
        text-style: bold dim;
        text-align: center;
        color: $text-muted;
        height: 1;
    }

    #status-rclone, #status-timer, #status-sync, #status-vault {
        height: 1;
        padding: 0;
    }
    """

    def compose(self) -> ComposeResult:
        # "KOS Capture" as single ansi_shadow string exceeds 80 cols — render separately.
        banner = (
            pyfiglet.figlet_format("KOS", font="ansi_shadow").rstrip()
            + "\n"
            + pyfiglet.figlet_format("Capture", font="calvin_s").rstrip()
        )

        with Center():
            with Vertical(id="container"):
                yield Static(banner, id="banner")
                yield Static("─" * 54, id="separator-top")
                yield Static(
                    "Capture freely. Organize strategically  —  v1.0.0",
                    id="tagline",
                )
                yield Static("─" * 40, id="separator-bottom")

                with Center():
                    with Vertical(id="nav-panel"):
                        yield Static("Main Menu", id="nav-title")
                        yield Static("─" * 22, id="nav-separator")
                        yield ListView(
                            *[
                                ListItem(Label(label), id=item_id)
                                for label, item_id in _NAV_ITEMS
                            ],
                            id="nav-list",
                        )

                with Center():
                    with Vertical(id="status-panel"):
                        yield Static("[ System Status ]", id="status-title")
                        yield Static("", id="status-rclone")
                        yield Static("", id="status-timer")
                        yield Static("", id="status-sync")
                        yield Static("", id="status-vault")

    def on_mount(self) -> None:
        self._update_status()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle Enter on a nav menu item."""
        dispatch = {
            "nav-sync":       self.action_go_sync,
            "nav-inbox":      self.action_go_inbox,
            "nav-transcribe": self.action_go_transcribe,
            "nav-config":     self.action_go_config,
            "nav-refresh":    self.action_refresh_status,
            "nav-quit":       self.app.exit,
        }
        fn = dispatch.get(event.item.id)
        if fn:
            fn()

    def action_go_sync(self) -> None:
        self.app.switch_screen("sync")

    def action_go_inbox(self) -> None:
        self.app.switch_screen("inbox")

    def action_go_transcribe(self) -> None:
        self.app.switch_screen("transcribe")

    def action_go_config(self) -> None:
        self.app.push_screen("setup")

    def action_refresh_status(self) -> None:
        self._update_status(show_errors=True, show_notification=True)

    def _update_status(self, show_errors: bool = False, show_notification: bool = False) -> None:
        """Query core modules and update each status widget."""
        status = rclone.status()

        self.query_one("#status-rclone", Static).update(
            _status_line(status.installed, "rclone installed")
        )
        self.query_one("#status-timer", Static).update(
            _status_line(status.timer_active, "proton-sync.timer active")
        )

        if status.last_sync:
            sync_str = status.last_sync.strftime("%Y-%m-%d %I:%M %p")
            self.query_one("#status-sync", Static).update(
                _status_line(True, f"last sync  {sync_str}")
            )
        else:
            self.query_one("#status-sync", Static).update(
                _status_line(False, "last sync  never")
            )

        vault_ok = False
        config_error: str | None = None
        if config.exists():
            try:
                cfg = config.load()
                vault_ok = cfg.vault_root.exists()
            except Exception as exc:
                config_error = str(exc)

        self.query_one("#status-vault", Static).update(
            _status_line(vault_ok, "KOS vault detected")
        )

        if show_errors and config_error:
            self.app.push_screen(
                ErrorModal(f"{config_error}\n\nOpen Setup to fix your configuration."),
                self._on_error_modal_dismiss,
            )
        elif show_notification and status.installed and vault_ok:
            self.notify("All systems connected.", severity="information")

    def _on_error_modal_dismiss(self, result: str | None) -> None:
        if result == "setup":
            self.app.push_screen("setup")
