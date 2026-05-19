"""
tests/test_setup_screen.py

Integration tests for screens/setup.py using Textual's Pilot harness.

Covers the three-field setup form: proton_drive, vault_root, remote_path.
"""

from unittest.mock import patch

from textual.widgets import Button, Input, Static

from app import KosCaptureApp


async def test_setup_screen_renders():
    """Setup screen composes without errors and the Save button is present."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            assert pilot.app.screen.query_one("#save-btn") is not None
            assert pilot.app.screen.query_one("#remote-path") is not None


async def test_empty_inputs_show_required_error():
    """Clicking Save with all inputs empty shows the required-fields message."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            pilot.app.screen.query_one("#save-btn", Button).press()
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "required" in errors.lower()


async def test_invalid_paths_show_not_found_error():
    """Submitting non-existent local paths surfaces path-not-found errors."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            pilot.app.screen.query_one("#proton-drive", Input).value = "/nonexistent/proton"
            pilot.app.screen.query_one("#vault-root", Input).value = "/nonexistent/vault"
            pilot.app.screen.query_one("#remote-path", Input).value = "Photos/Field-Notes"
            pilot.app.screen.query_one("#save-btn", Button).press()
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "not found" in errors.lower()


async def test_valid_paths_call_config_write(tmp_path):
    """Submitting valid inputs calls config.write() with all three arguments."""
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()

    with patch("app.config.exists", return_value=False), \
         patch("screens.setup.config.write") as mock_write, \
         patch("screens.setup.config.validate", return_value=[]):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            pilot.app.screen.query_one("#proton-drive", Input).value = str(proton)
            pilot.app.screen.query_one("#vault-root", Input).value = str(vault)
            pilot.app.screen.query_one("#remote-path", Input).value = "Photos/Field-Notes"
            pilot.app.screen.query_one("#save-btn", Button).press()
            await pilot.pause()
        mock_write.assert_called_once_with(str(proton), str(vault), "Photos/Field-Notes")
