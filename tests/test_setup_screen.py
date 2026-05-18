"""
tests/test_setup_screen.py

Integration tests for screens/setup.py using Textual's Pilot harness.

Runs the full app headlessly so the widget lifecycle fires correctly.
Widgets are queried via pilot.app.screen (the active screen) rather than
pilot.app — the app root only exposes the _default base screen, not
pushed screens. Input values are set directly on the Input widget since
pilot.type() does not exist in Textual 8.x.
"""

from unittest.mock import patch

from textual.widgets import Input, Static

from app import KosCaptureApp


async def test_setup_screen_renders():
    """Setup screen composes without errors and the Save button is present."""
    app = KosCaptureApp()
    with patch("app.config.exists", return_value=False):
        async with app.run_test() as pilot:
            await pilot.pause()
            assert pilot.app.screen.query_one("#save-btn") is not None


async def test_empty_inputs_show_required_error():
    """Clicking Save with both inputs empty shows the required-fields message."""
    app = KosCaptureApp()
    with patch("app.config.exists", return_value=False):
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#save-btn")
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "required" in errors.lower()


async def test_invalid_paths_show_not_found_error():
    """Submitting non-existent paths surfaces path-not-found errors."""
    app = KosCaptureApp()
    with patch("app.config.exists", return_value=False):
        async with app.run_test() as pilot:
            await pilot.pause()
            pilot.app.screen.query_one("#proton-drive", Input).value = "/nonexistent/proton"
            pilot.app.screen.query_one("#vault-root", Input).value = "/nonexistent/vault"
            await pilot.click("#save-btn")
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "not found" in errors.lower()


async def test_valid_paths_call_config_write(tmp_path):
    """Submitting valid paths calls config.write() with the correct arguments."""
    proton = tmp_path / "proton"
    vault = tmp_path / "vault"
    proton.mkdir()
    vault.mkdir()

    app = KosCaptureApp()
    with patch("app.config.exists", return_value=False), \
         patch("screens.setup.config.write") as mock_write, \
         patch("screens.setup.config.validate", return_value=[]):
        async with app.run_test() as pilot:
            await pilot.pause()
            pilot.app.screen.query_one("#proton-drive", Input).value = str(proton)
            pilot.app.screen.query_one("#vault-root", Input).value = str(vault)
            await pilot.click("#save-btn")
            await pilot.pause()
        mock_write.assert_called_once_with(str(proton), str(vault))
