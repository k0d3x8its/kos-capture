"""
tests/test_home_screen.py

Integration tests for screens/home.py using Textual's Pilot harness.

Strategy: always start on setup (config.exists=False), then explicitly
push "home" — avoids race between on_mount routing and the pilot harness.
"""

from datetime import datetime
from unittest.mock import patch

from textual.widgets import Static

from app import KosCaptureApp
from core.rclone import RcloneStatus


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
