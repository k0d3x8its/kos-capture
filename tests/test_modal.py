"""
tests/test_modal.py

Unit tests for screens/modal.py — ErrorModal rendering and button behavior.
"""

from unittest.mock import patch

from textual.widgets import Button, Static

from app import KosCaptureApp
from screens.modal import ErrorModal


async def test_modal_renders():
    """ErrorModal composes without errors and shows title and message."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.app.push_screen(ErrorModal("Something went wrong."))
            await pilot.pause()
            title = str(pilot.app.screen.query_one("#modal-title", Static).content)
            assert "configuration error" in title.lower()
            msg = str(pilot.app.screen.query_one("#modal-message", Static).content)
            assert "Something went wrong." in msg


async def test_modal_dismiss_button_closes():
    """Clicking Dismiss closes the modal and returns to the previous screen."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.app.push_screen("setup")
            await pilot.pause()
            await pilot.app.push_screen(ErrorModal("Error."))
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "ErrorModal"
            pilot.app.screen.query_one("#modal-dismiss", Button).press()
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "SetupScreen"


async def test_modal_escape_closes():
    """Pressing Escape closes the modal and returns to the previous screen."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.app.push_screen("setup")
            await pilot.pause()
            await pilot.app.push_screen(ErrorModal("Error."))
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "SetupScreen"


async def test_modal_setup_button_dismisses_with_setup():
    """Clicking Open Setup dismisses the modal with result 'setup'."""
    results = []

    def callback(result):
        results.append(result)

    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.app.push_screen(ErrorModal("Error."), callback)
            await pilot.pause()
            pilot.app.screen.query_one("#modal-setup", Button).press()
            await pilot.pause()
            assert results == ["setup"]
