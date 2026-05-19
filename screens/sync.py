"""
screens/sync.py

Sync screen — rclone/timer status and manual Proton Drive sync trigger.

The sync runs in a background Worker thread so the UI stays responsive.
stdout/stderr stream live into a RichLog. The trigger button is disabled
while a sync is in progress. Status refreshes automatically on completion.

Escape is blocked while a sync is running to avoid orphaning the process.
"""

import core.config as config
import core.rclone as rclone
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, RichLog, Static
from textual.worker import get_current_worker


def _status_line(ok: bool, label: str) -> str:
    icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
    return f"  {icon}  {label}"


class SyncScreen(Screen):

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("r", "refresh_status", "Refresh", show=False),
    ]

    DEFAULT_CSS = """
    SyncScreen {
        align: center middle;
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

    #status-box {
        height: auto;
        border: round $panel;
        padding: 0 1;
        margin-bottom: 1;
    }

    #status-rclone, #status-timer, #status-sync {
        height: 1;
        padding: 0;
    }

    #trigger-btn {
        width: 100%;
        margin-bottom: 1;
    }

    #sync-state {
        text-align: center;
        height: 1;
        padding: 0;
        margin-bottom: 1;
    }

    #log {
        height: 14;
        border: round $panel;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._sync_running = False

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static("Proton Drive Sync", id="title")

            with Vertical(id="status-box"):
                yield Static("", id="status-rclone")
                yield Static("", id="status-timer")
                yield Static("", id="status-sync")

            yield Button("Trigger Sync", id="trigger-btn", variant="primary")
            yield Static("", id="sync-state")
            yield RichLog(id="log", highlight=True, markup=True)

        yield Footer()

    def on_mount(self) -> None:
        self._refresh_status()

    # ── Bindings ───────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        """Return to Home — blocked while sync is running."""
        if not self._sync_running:
            self.app.switch_screen("home")
        else:
            self.query_one("#sync-state", Static).update(
                "[yellow]Sync in progress — wait for it to finish.[/yellow]"
            )

    def action_refresh_status(self) -> None:
        self._refresh_status()

    # ── Button ─────────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "trigger-btn" and not self._sync_running:
            self._start_sync()

    # ── Status ─────────────────────────────────────────────────────────────

    def _refresh_status(self) -> None:
        s = rclone.status()
        self.query_one("#status-rclone", Static).update(
            _status_line(s.installed, "rclone installed")
        )
        self.query_one("#status-timer", Static).update(
            _status_line(s.timer_active, "proton-sync.timer active")
        )
        if s.last_sync:
            ts = s.last_sync.strftime("%Y-%m-%d %I:%M %p")
            self.query_one("#status-sync", Static).update(
                _status_line(True, f"last sync  {ts}")
            )
        else:
            self.query_one("#status-sync", Static).update(
                _status_line(False, "last sync  never")
            )

    # ── Sync worker ────────────────────────────────────────────────────────

    def _start_sync(self) -> None:
        """Validate config, lock UI, clear log, then launch worker."""
        if not config.exists():
            self.query_one("#sync-state", Static).update(
                "[red]No config found — run setup first.[/red]"
            )
            return

        try:
            cfg = config.load()
        except Exception as exc:
            self.query_one("#sync-state", Static).update(
                f"[red]Config error: {exc}[/red]"
            )
            return

        self._sync_running = True
        self.query_one("#trigger-btn", Button).disabled = True
        self.query_one("#sync-state", Static).update("[yellow]⟳  Syncing…[/yellow]")
        self.query_one("#log", RichLog).clear()
        self._run_sync(str(cfg.proton_drive))

    @work(thread=True)
    def _run_sync(self, proton_drive: str) -> None:
        """Background thread: stream rclone output line-by-line into the log."""
        worker = get_current_worker()
        log = self.query_one("#log", RichLog)
        exit_code = -1

        try:
            proc = rclone.trigger_sync(proton_drive)
            for line in proc.stdout:
                if worker.is_cancelled:
                    proc.terminate()
                    break
                self.app.call_from_thread(log.write, line.rstrip())
            proc.wait()
            exit_code = proc.returncode
        except Exception as exc:
            self.app.call_from_thread(log.write, f"[red]Error: {exc}[/red]")

        self.app.call_from_thread(self._on_sync_complete, exit_code)

    def _on_sync_complete(self, exit_code: int) -> None:
        """Called on the main thread after the worker finishes."""
        self._sync_running = False
        self.query_one("#trigger-btn", Button).disabled = False

        if exit_code == 0:
            self.query_one("#sync-state", Static).update(
                "[green]✓  Sync complete.[/green]"
            )
        else:
            self.query_one("#sync-state", Static).update(
                f"[red]✗  Sync failed (exit {exit_code}).[/red]"
            )

        self._refresh_status()
