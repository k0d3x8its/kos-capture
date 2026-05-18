"""
screens/home.py

Home screen — first screen seen after setup completes.

Shows:
  - ASCII art title via pyfiglet (roman font)
  - System status summary: rclone installed, sync timer active,
    vault detected, last sync time
  - Keybinding hints via Footer

'r' refreshes status in-place without leaving the screen.
'c' opens the Setup/Config screen.
"""

import pyfiglet

import core.config as config
import core.rclone as rclone
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static


def _status_line(ok: bool, label: str) -> str:
    """Format a coloured ✓/✗ status line using Rich markup."""
    icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
    return f"  {icon}  {label}"


class HomeScreen(Screen):

    BINDINGS = [
        # Defined as methods below so Screen-level bindings fire reliably
        # regardless of which child widget holds focus.
        Binding("r", "refresh_status", "Refresh"),
        Binding("c", "open_config", "Config"),
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

    #status-panel {
        width: 52;
        height: auto;
        border: round $primary;
        padding: 1 2;
        margin-bottom: 1;
    }

    #status-title {
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        # Render separately — "KOS Capture" as one string exceeds 80 cols in ansi_shadow.
        # KOS: heavy ansi_shadow block chars. Capture: lighter shadow font below it.
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
                with Vertical(id="status-panel"):
                    yield Static("[ System Status ]", id="status-title")
                    yield Static("", id="status-rclone")
                    yield Static("", id="status-timer")
                    yield Static("", id="status-sync")
                    yield Static("", id="status-vault")

        yield Footer()

    def on_mount(self) -> None:
        """Populate status on first load."""
        self._update_status()

    def action_refresh_status(self) -> None:
        """Re-check all status values — bound to 'r'."""
        self._update_status()

    def action_open_config(self) -> None:
        """Push the setup/config screen — bound to 'c'."""
        self.app.push_screen("setup")

    def _update_status(self) -> None:
        """Query core modules and update each status widget."""
        status = rclone.status()

        self.query_one("#status-rclone", Static).update(
            _status_line(status.installed, "rclone installed")
        )
        self.query_one("#status-timer", Static).update(
            _status_line(status.timer_active, "proton-sync.timer active")
        )

        # 12-hour AM/PM format for last sync time
        if status.last_sync:
            sync_str = status.last_sync.strftime("%Y-%m-%d %I:%M %p")
            self.query_one("#status-sync", Static).update(
                _status_line(True, f"last sync  {sync_str}")
            )
        else:
            self.query_one("#status-sync", Static).update(
                _status_line(False, "last sync  never")
            )

        # Vault — verify vault_root path exists on disk
        vault_ok = False
        if config.exists():
            try:
                cfg = config.load()
                vault_ok = cfg.vault_root.exists()
            except Exception:
                pass

        self.query_one("#status-vault", Static).update(
            _status_line(vault_ok, "KOS vault detected")
        )
