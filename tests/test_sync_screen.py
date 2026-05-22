"""
tests/test_sync_screen.py

Integration tests for screens/sync.py using Textual's Pilot harness.

Strategy: start on setup (config.exists=False by default for routing),
then push "sync" explicitly. Tests cover status population, button state
management, config-missing guard, sync completion callback, and Escape
blocking during an active sync.
"""

from unittest.mock import MagicMock, patch
from datetime import datetime

from textual.widgets import Button, RichLog, Static

from app import KosCaptureApp
from core.rclone import RcloneStatus
from screens.sync import _fmt_log_line, _to_mbps


def _make_status(installed=True, timer=True, last_sync=None):
    return RcloneStatus(installed=installed, timer_active=timer, last_sync=last_sync)


async def _open_sync(pilot):
    await pilot.app.push_screen("sync")
    await pilot.pause()


async def test_sync_screen_renders():
    """Sync screen composes without errors and key widgets are present."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            assert pilot.app.screen.query_one("#trigger-btn") is not None
            assert pilot.app.screen.query_one("#log", RichLog) is not None


async def test_status_populates_on_mount():
    """Status widgets are filled after mount."""
    status = _make_status(installed=True, timer=True)
    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            rclone_text = str(pilot.app.screen.query_one("#status-rclone", Static).content)
            assert "rclone" in rclone_text.lower()
            timer_text = str(pilot.app.screen.query_one("#status-timer", Static).content)
            assert "timer" in timer_text.lower()


async def test_last_sync_never_when_none():
    """Status shows 'never' when last_sync is None."""
    status = _make_status(last_sync=None)
    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            sync_text = str(pilot.app.screen.query_one("#status-sync", Static).content)
            assert "never" in sync_text.lower()


async def test_last_sync_formatted_when_present():
    """Status shows AM/PM formatted datetime when last_sync is set."""
    status = _make_status(last_sync=datetime(2025, 5, 18, 14, 30))
    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            sync_text = str(pilot.app.screen.query_one("#status-sync", Static).content)
            assert "AM" in sync_text or "PM" in sync_text


async def test_trigger_btn_enabled_on_mount():
    """Trigger Sync button starts enabled."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            btn = pilot.app.screen.query_one("#trigger-btn", Button)
            assert not btn.disabled


async def test_no_config_shows_error():
    """Pressing Trigger Sync with no config shows an error message."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status), \
         patch("screens.sync.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            pilot.app.screen.query_one("#trigger-btn", Button).press()
            await pilot.pause()
            state_text = str(pilot.app.screen.query_one("#sync-state", Static).content)
            assert "config" in state_text.lower()


async def test_sync_complete_callback_re_enables_button():
    """_on_sync_complete(0) re-enables the button and shows success."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            screen = pilot.app.screen
            # Simulate a completed sync directly via the callback
            screen._sync_running = True
            screen.query_one("#trigger-btn", Button).disabled = True
            screen._on_sync_complete(0)
            await pilot.pause()
            assert not screen.query_one("#trigger-btn", Button).disabled
            state_text = str(screen.query_one("#sync-state", Static).content)
            assert "complete" in state_text.lower()


async def test_sync_failed_callback_shows_exit_code():
    """_on_sync_complete(non-zero) shows failure with exit code."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            screen = pilot.app.screen
            screen._sync_running = True
            screen.query_one("#trigger-btn", Button).disabled = True
            screen._on_sync_complete(1)
            await pilot.pause()
            state_text = str(screen.query_one("#sync-state", Static).content)
            assert "failed" in state_text.lower()


async def test_escape_blocked_during_sync():
    """Pressing Escape while sync is running shows a warning, not navigate."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            screen = pilot.app.screen
            screen._sync_running = True
            await pilot.press("escape")
            await pilot.pause()
            # Still on sync screen
            assert pilot.app.screen is screen


async def test_escape_navigates_when_idle():
    """Pressing Escape when no sync is running switches back to home."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "HomeScreen"


async def test_trigger_sync_exception_re_enables_button():
    """If trigger_sync raises, the finally block still re-enables the button."""
    status = _make_status()
    mock_cfg = MagicMock()
    mock_cfg.proton_drive = "/mock/path"
    mock_cfg.remote_path = "Photos/Field-Notes"

    with patch("app.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status), \
         patch("screens.sync.config.exists", return_value=True), \
         patch("screens.sync.config.load", return_value=mock_cfg), \
         patch("screens.sync.rclone.trigger_sync", side_effect=OSError("mock failure")):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_sync(pilot)
            pilot.app.screen.query_one("#trigger-btn", Button).press()
            await pilot.pause()
            await pilot.pause()
            btn = pilot.app.screen.query_one("#trigger-btn", Button)
            assert not btn.disabled
            assert pilot.app.screen._sync_running is False


# ── _to_mbps() unit tests ────────────────────────────────────────────────────

def test_to_mbps_bytes_per_second():
    """_to_mbps() converts B/s to Mbps."""
    result = _to_mbps(1_000_000, "B")
    assert "Mbps" in result


def test_to_mbps_mib_per_second():
    """_to_mbps() converts MiB/s correctly."""
    result = _to_mbps(10.0, "MiB")
    assert "Mbps" in result
    val = float(result.split()[0])
    assert val > 0


def test_to_mbps_gib_produces_gbps():
    """_to_mbps() uses Gbps label when speed >= 1000 Mbps."""
    result = _to_mbps(1.0, "GiB")
    assert "Gbps" in result


# ── _fmt_log_line() unit tests ───────────────────────────────────────────────

def test_fmt_log_line_file_copied():
    """Per-file Copied entry produces timestamped arrow line."""
    raw = "2026/05/18 14:30:00 INFO  : raw/Field-Logs/FL-vol-001/scan.pdf: Copied (new)"
    out = _fmt_log_line(raw)
    assert out is not None
    assert "2:30:00 PM" in out
    assert "scan.pdf" in out
    assert "⟹" in out
    assert "Copied" in out


def test_fmt_log_line_file_skipped():
    """Per-file Skipped entry formats correctly."""
    raw = "2026/05/18 09:05:00 INFO  : raw/Field-Logs/FL-vol-001/scan.pdf: Skipped (same size)"
    out = _fmt_log_line(raw)
    assert out is not None
    assert "Skipped" in out


def test_fmt_log_line_blank_info_returns_none():
    """INFO line with no rest content is dropped (returns None)."""
    raw = "2026/05/18 14:30:00 INFO  : "
    out = _fmt_log_line(raw)
    assert out is None


def test_fmt_log_line_blank_line_returns_none():
    """Completely blank line returns None."""
    assert _fmt_log_line("") is None
    assert _fmt_log_line("   ") is None


def test_fmt_log_line_checks_all_new():
    """Checks line with verified=0 returns None (all files were new, nothing to report)."""
    raw = "Checks: 0 / 10, Listed 10"
    out = _fmt_log_line(raw)
    assert out is None


def test_fmt_log_line_checks_some_existing():
    """Checks line with verified>0 reports already-downloaded count."""
    raw = "Checks: 3 / 10"
    out = _fmt_log_line(raw)
    assert out is not None
    assert "Already downloaded: 3" in out
    assert "files" in out


def test_fmt_log_line_checks_singular():
    """Checks line with verified=1 uses singular 'file'."""
    raw = "Checks: 1 / 5"
    out = _fmt_log_line(raw)
    assert out is not None
    assert "1 file" in out


def test_fmt_log_line_count_transferred():
    """Count-based Transferred line becomes 'Files synced: N / M (P%)'."""
    raw = "Transferred: 3 / 5, 60%"
    out = _fmt_log_line(raw)
    assert out is not None
    assert "Files synced: 3 / 5 (60%)" == out


def test_fmt_log_line_speed_converted():
    """Speed values in summary lines are converted to Mbps/Gbps."""
    raw = "Transferred: 100 MiB in 10s, 10.0 MiB/s"
    out = _fmt_log_line(raw)
    assert out is not None
    assert "MiB/s" not in out
    assert "Mbps" in out or "Gbps" in out


def test_fmt_log_line_size_converted():
    """IEC size units in summary lines are normalised."""
    raw = "Transferred: 512 MiB"
    out = _fmt_log_line(raw)
    assert out is not None
    assert "MiB" not in out
    assert "MB" in out


def test_fmt_log_line_midnight_am():
    """Hour 0 formats as 12:xx:xx AM."""
    raw = "2026/05/18 00:05:00 INFO  : some/file.pdf: Copied (new)"
    out = _fmt_log_line(raw)
    assert out is not None
    assert "12:05:00 AM" in out


def test_fmt_log_line_noon_pm():
    """Hour 12 formats as 12:xx:xx PM."""
    raw = "2026/05/18 12:00:00 INFO  : some/file.pdf: Copied (new)"
    out = _fmt_log_line(raw)
    assert out is not None
    assert "12:00:00 PM" in out
