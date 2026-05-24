"""
tests/test_home_screen.py

Integration tests for screens/home.py using Textual's Pilot harness.

Strategy: always start on setup (config.exists=False), then explicitly
push "home" — avoids race between on_mount routing and the pilot harness.

Navigation menu tests verify both letter-key shortcuts and arrow+Enter paths.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from textual.widgets import ListView, Static

from app import KosCaptureApp
from core.rclone import RcloneStatus
from screens.home import _status_line


def _make_status(installed=True, timer=True, last_sync=None):
    return RcloneStatus(installed=installed, timer_active=timer, last_sync=last_sync)


async def _open_home(pilot):
    """Navigate to home screen from whatever the current screen is."""
    await pilot.app.push_screen("home")
    await pilot.pause()


async def test_home_screen_renders():
    """Home screen composes without errors and key widgets are present."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            assert pilot.app.screen.query_one("#banner") is not None
            assert pilot.app.screen.query_one("#status-panel") is not None
            assert pilot.app.screen.query_one("#separator-top") is not None
            assert pilot.app.screen.query_one("#separator-bottom") is not None
            assert pilot.app.screen.query_one("#tagline") is not None


async def test_status_widgets_populate_on_mount():
    """Status widgets contain text after mount (not empty strings)."""
    status = _make_status(installed=True, timer=True)
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            rclone_text = str(pilot.app.screen.query_one("#status-rclone", Static).content)
            assert "rclone" in rclone_text.lower()
            timer_text = str(pilot.app.screen.query_one("#status-timer", Static).content)
            assert "timer" in timer_text.lower()


async def test_last_sync_never_when_none():
    """Status shows 'never' when last_sync is None."""
    status = _make_status(last_sync=None)
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            sync_text = str(pilot.app.screen.query_one("#status-sync", Static).content)
            assert "never" in sync_text.lower()


async def test_last_sync_formatted_when_present():
    """Status shows AM/PM formatted datetime when last_sync is set."""
    status = _make_status(last_sync=datetime(2025, 5, 18, 14, 30))
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            sync_text = str(pilot.app.screen.query_one("#status-sync", Static).content)
            assert "PM" in sync_text or "AM" in sync_text


async def test_r_key_refreshes_status():
    """Pressing 'r' calls rclone.status() a second time."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status) as mock_status, \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            calls_after_mount = mock_status.call_count
            await pilot.press("r")
            await pilot.pause()
            assert mock_status.call_count == calls_after_mount + 1


async def test_c_key_pushes_setup_screen():
    """Pressing 'c' navigates to the setup screen."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            await pilot.press("c")
            await pilot.pause()
            assert pilot.app.screen.query_one("#save-btn") is not None


async def test_nav_menu_present():
    """Navigation ListView and all six items are in the DOM."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            lv = pilot.app.screen.query_one("#nav-list", ListView)
            assert lv is not None
            assert len(lv.children) == 7


async def test_enter_on_config_item_pushes_setup():
    """Arrow-down to Config item then Enter navigates to setup screen."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            # ListView starts on index 0 (Sync); move down 4 times to reach Config (index 4)
            await pilot.press("down", "down", "down", "down")
            await pilot.press("enter")
            await pilot.pause()
            assert pilot.app.screen.query_one("#save-btn") is not None


async def test_enter_on_refresh_item_calls_status():
    """Arrow-down to Refresh item then Enter calls rclone.status() again."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status) as mock_status, \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            calls_after_mount = mock_status.call_count
            # Move down 5 times to reach Refresh (index 5)
            await pilot.press("down", "down", "down", "down", "down")
            await pilot.press("enter")
            await pilot.pause()
            assert mock_status.call_count == calls_after_mount + 1


async def test_s_key_navigates_to_sync():
    """Pressing 's' switches to the Sync screen."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False), \
         patch("screens.sync.rclone.status", return_value=status):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            await pilot.press("s")
            await pilot.pause()
            assert pilot.app.screen.query_one("#trigger-btn") is not None


async def test_i_key_navigates_to_inbox():
    """Pressing 'i' switches to the Inbox screen."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False), \
         patch("screens.inbox.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            await pilot.press("i")
            await pilot.pause()
            assert pilot.app.screen.query_one("#file-list") is not None


async def test_refresh_with_bad_config_shows_modal():
    """Pressing 'r' when config is malformed pushes the ErrorModal."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=True), \
         patch("screens.home.config.load", side_effect=ValueError("Config file is not valid TOML: bad")):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            await pilot.press("r")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "ErrorModal"


async def test_refresh_all_ok_shows_notification(tmp_path):
    """Pressing 'r' when all systems OK triggers a notify toast."""
    vault = tmp_path / "vault"
    vault.mkdir()
    status = _make_status(installed=True, timer=True)

    from unittest.mock import MagicMock
    mock_cfg = MagicMock()
    mock_cfg.vault_root = vault

    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=True), \
         patch("screens.home.config.load", return_value=mock_cfg):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            with patch.object(pilot.app.screen, "notify") as mock_notify:
                await pilot.press("r")
                await pilot.pause()
                mock_notify.assert_called_once()
                args, kwargs = mock_notify.call_args
                assert "connected" in args[0].lower()


async def test_t_key_navigates_to_transcribe():
    """Pressing 't' switches to the Transcribe screen."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            await pilot.press("t")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "TranscribeScreen"


async def test_last_sync_midnight_shows_12am():
    """Hour 0 (midnight) formats as 12:xx AM, not 0:xx AM."""
    status = _make_status(last_sync=datetime(2026, 5, 18, 0, 5))
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            sync_text = str(pilot.app.screen.query_one("#status-sync", Static).content)
            assert "12:05" in sync_text
            assert "AM" in sync_text


async def test_last_sync_noon_shows_12pm():
    """Hour 12 (noon) formats as 12:xx PM, not 0:xx PM."""
    status = _make_status(last_sync=datetime(2026, 5, 18, 12, 0))
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            sync_text = str(pilot.app.screen.query_one("#status-sync", Static).content)
            assert "12:00" in sync_text
            assert "PM" in sync_text


async def test_error_modal_dismiss_setup_pushes_setup_screen():
    """_on_error_modal_dismiss('setup') navigates to the setup screen."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            screen = pilot.app.screen
            screen._on_error_modal_dismiss("setup")
            await pilot.pause()
            assert pilot.app.screen.query_one("#save-btn") is not None


# ── _status_line() pure function ──────────────────────────────────────────────

def test_status_line_ok_contains_checkmark():
    """ok=True produces a ✓ icon in the output."""
    out = _status_line(True, "rclone installed")
    assert "✓" in out
    assert "rclone installed" in out


def test_status_line_fail_contains_cross():
    """ok=False produces a ✗ icon in the output."""
    out = _status_line(False, "rclone installed")
    assert "✗" in out
    assert "rclone installed" in out


def test_status_line_ok_uses_green():
    """ok=True uses green Rich markup."""
    out = _status_line(True, "label")
    assert "#00ff00" in out or "green" in out


def test_status_line_fail_uses_red():
    """ok=False uses red Rich markup."""
    out = _status_line(False, "label")
    assert "[bold red]" in out


def test_status_line_ok_false_never_shows_checkmark():
    """ok=False must not contain ✓ — avoids confusing mixed output."""
    assert "✓" not in _status_line(False, "any label")


def test_status_line_ok_true_never_shows_cross():
    """ok=True must not contain ✗ — avoids confusing mixed output."""
    assert "✗" not in _status_line(True, "any label")


# ── action_go_ready() logic ───────────────────────────────────────────────────

async def test_v_key_no_results_shows_warning():
    """Pressing 'v' with empty session_results shows a warning notification."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            pilot.app.session_results = []
            with patch.object(pilot.app.screen, "notify") as mock_notify:
                await pilot.press("v")
                await pilot.pause()
                mock_notify.assert_called_once()
                _, kwargs = mock_notify.call_args
                assert kwargs.get("severity") == "warning"


async def test_v_key_with_results_navigates_to_ready(tmp_path):
    """Pressing 'v' with session_results switches to ReadyScreen."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            pilot.app.session_results = [tmp_path / "note.pdf"]
            await pilot.press("v")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "ReadyScreen"


async def test_on_error_modal_dismiss_none_does_not_navigate():
    """_on_error_modal_dismiss(None) stays on HomeScreen — Dismiss button path."""
    status = _make_status()
    with patch("app.config.exists", return_value=False), \
         patch("screens.home.rclone.status", return_value=status), \
         patch("screens.home.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_home(pilot)
            home = pilot.app.screen
            home._on_error_modal_dismiss(None)
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "HomeScreen"
