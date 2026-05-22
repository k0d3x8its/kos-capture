"""
screens/sync.py

Sync screen — rclone/timer status and manual Proton Drive sync trigger.

The sync runs in a background Worker thread so the UI stays responsive.
stdout/stderr stream live into a RichLog. The trigger button is disabled
while a sync is in progress. Status refreshes automatically on completion.

Escape is blocked while a sync is running to avoid orphaning the process.
"""

import re

import core.config as config
import core.rclone as rclone
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, RichLog, Static
from textual.worker import get_current_worker


_LOG_RE        = re.compile(r'^(\d{4}/\d{2}/\d{2}) (\d{2}):(\d{2}):(\d{2}) \w+\s+:\s*(.*)')
_ACTION_RE     = re.compile(r':\s+(Copied|Deleted|Skipped|Updated|Moved|Renamed)')
_SPEED_RE      = re.compile(r'([\d.]+)\s*(TiB|GiB|MiB|KiB|B)/s')
_SIZE_RE       = re.compile(r'([\d.]+)\s*(TiB|GiB|MiB|KiB|B)(?!/)')
_CHECKS_RE     = re.compile(r'Checks:\s*(\d+)\s*/\s*(\d+)(?:,[^,]*)?(?:,\s*Listed\s+(\d+))?')
_COUNT_XFER_RE = re.compile(r'^Transferred:\s+(\d+)\s*/\s*(\d+),\s*(\d+)%')

_IEC_LABEL  = {'TiB': 'TB', 'GiB': 'GB', 'MiB': 'MB', 'KiB': 'KB', 'B': 'B'}
_IEC_BITS   = {'TiB': 8_796_093_022_208, 'GiB': 8_589_934_592,
               'MiB': 8_388_608, 'KiB': 8_192, 'B': 8}

_PATH_COL = 31   # fixed column width for file path before arrow


def _to_mbps(val: float, unit: str) -> str:
    mbps = val * _IEC_BITS.get(unit, 1) / 1_000_000
    return f"{mbps / 1000:.2f} Gbps" if mbps >= 1000 else f"{mbps:.1f} Mbps"


def _fmt_log_line(raw: str) -> str | None:
    line = raw.rstrip()

    # Per-file entry: "2024/01/15 14:30:00 INFO  : path: Copied (new)"
    m = _LOG_RE.match(line)
    if m:
        _, hh, mm, ss, rest = m.groups()
        rest = rest.strip()
        if not rest:
            return None  # skip blank INFO lines
        h = int(hh)
        h12 = h % 12 or 12
        ampm = "AM" if h < 12 else "PM"
        ts = f"{h12}:{mm}:{ss} {ampm}"
        am = _ACTION_RE.search(rest)
        if am:
            path   = rest[:am.start()].rstrip(": ")
            action = am.group(1) + rest[am.end():]
            if len(path) > _PATH_COL:
                path_padded = ("…" + path[-((_PATH_COL - 1)):]).ljust(_PATH_COL)
            else:
                path_padded = path.ljust(_PATH_COL)
            return f"{ts}  {path_padded}  ⟹  {action}"
        return f"{ts}  {rest}"

    # Collapse tabs/extra spaces for all summary lines
    clean = re.sub(r'[ \t]+', ' ', line).strip()
    if not clean:
        return None

    # Checks: N / M — files rclone compared against destination (0 = all were new)
    m = _CHECKS_RE.search(clean)
    if m:
        verified, total, listed = m.group(1), m.group(2), m.group(3)
        if verified == "0":
            return f"Files scanned: {listed}" if listed else None
        noun = "file" if verified == "1" else "files"
        scanned = f"\nFiles scanned: {listed}" if listed else ""
        return f"Already downloaded: {verified} {noun}{scanned}"

    # Count-based Transferred (files, not bytes) — rename to avoid duplicate label
    m = _COUNT_XFER_RE.match(clean)
    if m:
        done, total, pct = m.group(1), m.group(2), m.group(3)
        return f"Files synced: {done} / {total} ({pct}%)"

    # Convert speed then rename IEC size units for remaining lines
    clean = _SPEED_RE.sub(lambda m: _to_mbps(float(m.group(1)), m.group(2)), clean)
    clean = _SIZE_RE.sub(lambda m: f"{float(m.group(1)):.1f} {_IEC_LABEL[m.group(2)]}", clean)
    return clean


def _status_line(ok: bool, label: str) -> str:
    icon = "[bold #00ff00]✓[/bold #00ff00]" if ok else "[bold red]✗[/bold red]"
    return f"  {icon}  {label}"


class SyncScreen(Screen):

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("r", "refresh_status", "Refresh", show=False),
    ]

    DEFAULT_CSS = """
    SyncScreen {
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

    #status-box {
        height: auto;
        border: round $panel;
        padding: 0 1;
        margin-bottom: 1;
    }

    #status-rclone, #status-timer, #status-sync {
        height: auto;
        padding: 0;
    }

    #trigger-btn {
        width: 100%;
        margin-bottom: 1;
        background: #00ff00;
        color: #000000;
    }

    #trigger-btn:hover {
        background: #33ff33;
        color: #000000;
    }

    #sync-state {
        text-align: center;
        height: 1;
        padding: 0;
        margin-bottom: 1;
    }

    #log {
        height: 12;
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
            yield RichLog(id="log", highlight=True, markup=True, wrap=True)

        yield Footer()

    def on_mount(self) -> None:
        self._refresh_status()
        self.query_one("#log", RichLog).focus()

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
            _dt = s.last_sync
            _h  = _dt.hour
            ts  = (f"{_dt.year}-{_dt.month:02d}-{_dt.day:02d} "
                   f"{_h % 12 or 12}:{_dt.minute:02d} {'AM' if _h < 12 else 'PM'}")
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
        self._run_sync(str(cfg.proton_drive), cfg.remote_path)

    @work(thread=True)
    def _run_sync(self, proton_drive: str, remote_path: str) -> None:
        """Background thread: stream rclone output line-by-line into the log."""
        worker = get_current_worker()
        log = self.query_one("#log", RichLog)
        exit_code = -1
        proc = None

        try:
            proc = rclone.trigger_sync(proton_drive, remote_path)
            for line in proc.stdout:
                if worker.is_cancelled:
                    proc.terminate()
                    break
                formatted = _fmt_log_line(line)
                if formatted is not None:
                    self.app.call_from_thread(log.write, formatted)
            proc.wait()
            exit_code = proc.returncode
        except Exception as exc:
            self.app.call_from_thread(log.write, f"[red]Error: {exc}[/red]")
            if proc is not None:
                proc.terminate()
        finally:
            self.app.call_from_thread(self._on_sync_complete, exit_code)

    def _on_sync_complete(self, exit_code: int) -> None:
        """Called on the main thread after the worker finishes."""
        self._sync_running = False
        self.query_one("#trigger-btn", Button).disabled = False

        if exit_code == 0:
            self.query_one("#sync-state", Static).update(
                "[#00ff41]✓  Sync complete.[/#00ff41]"
            )
        else:
            self.query_one("#sync-state", Static).update(
                f"[red]✗  Sync failed (exit {exit_code}).[/red]"
            )

        self._refresh_status()
