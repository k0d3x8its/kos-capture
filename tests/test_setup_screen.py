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


async def test_existing_config_prefills_inputs(tmp_path):
    """Opening Setup when config exists pre-fills all three input fields."""
    from unittest.mock import MagicMock
    import core.config as config_module

    mock_cfg = MagicMock()
    mock_cfg.proton_drive = tmp_path / "proton"
    mock_cfg.vault_root = tmp_path / "vault"
    mock_cfg.remote_path = "Photos/Field-Notes"

    with patch("app.config.exists", return_value=True), \
         patch("screens.setup.config.exists", return_value=True), \
         patch("screens.setup.config.load", return_value=mock_cfg):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.app.push_screen("setup")
            await pilot.pause()
            assert pilot.app.screen.query_one("#proton-drive", Input).value == str(mock_cfg.proton_drive)
            assert pilot.app.screen.query_one("#vault-root", Input).value == str(mock_cfg.vault_root)
            assert pilot.app.screen.query_one("#remote-path", Input).value == "Photos/Field-Notes"


async def test_error_clears_on_next_save_attempt(tmp_path):
    """Errors from a previous failed save are cleared when Save is clicked again."""
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()

    with patch("app.config.exists", return_value=False), \
         patch("screens.setup.config.write"), \
         patch("screens.setup.config.validate", return_value=[]), \
         patch("screens.setup.rclone.check_remote", return_value=True):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            # First save with empty fields — produces error
            pilot.app.screen.query_one("#save-btn", Button).press()
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert errors != ""
            # Fill valid values and save again — old error must be gone immediately
            pilot.app.screen.query_one("#proton-drive", Input).value = str(proton)
            pilot.app.screen.query_one("#vault-root", Input).value = str(vault)
            pilot.app.screen.query_one("#remote-path", Input).value = "Photos/Field-Notes"
            pilot.app.screen.query_one("#save-btn", Button).press()
            await pilot.pause()
            # Error widget now shows "Connecting..." — old error is gone
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "required" not in errors.lower()


async def test_valid_paths_call_config_write(tmp_path):
    """Submitting valid inputs calls config.write() with all three arguments."""
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()

    with patch("app.config.exists", return_value=False), \
         patch("screens.setup.config.write") as mock_write, \
         patch("screens.setup.config.validate", return_value=[]), \
         patch("screens.setup.rclone.check_remote", return_value=True):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            pilot.app.screen.query_one("#proton-drive", Input).value = str(proton)
            pilot.app.screen.query_one("#vault-root", Input).value = str(vault)
            pilot.app.screen.query_one("#remote-path", Input).value = "Photos/Field-Notes"
            pilot.app.screen.query_one("#save-btn", Button).press()
            await pilot.pause()  # worker starts
            await pilot.pause()  # call_from_thread fires _on_remote_check_done
            mock_write.assert_called_once_with(str(proton), str(vault), "Photos/Field-Notes")


async def test_connecting_message_shown_during_remote_check(tmp_path):
    """After local validation passes, 'Connecting' message appears and Save is disabled."""
    import threading
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()

    # Block check_remote in its worker thread so we can observe the transient state.
    gate = threading.Event()

    def slow_check(remote_path):
        gate.wait(timeout=5)
        return True

    with patch("app.config.exists", return_value=False), \
         patch("screens.setup.config.validate", return_value=[]), \
         patch("screens.setup.rclone.check_remote", side_effect=slow_check), \
         patch("screens.setup.config.write"):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            pilot.app.screen.query_one("#proton-drive", Input).value = str(proton)
            pilot.app.screen.query_one("#vault-root", Input).value = str(vault)
            pilot.app.screen.query_one("#remote-path", Input).value = "Photos/Field-Notes"
            pilot.app.screen.query_one("#save-btn", Button).press()
            await pilot.pause()  # _save() runs; worker blocks at gate.wait()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "connecting" in errors.lower()
            assert pilot.app.screen.query_one("#save-btn", Button).disabled
            gate.set()           # release worker
            await pilot.pause()  # worker completes, call_from_thread queued
            await pilot.pause()  # _on_remote_check_done fires


async def test_remote_not_found_shows_error_and_re_enables_button(tmp_path):
    """When check_remote returns False, an error is shown, Save re-enables, config not written."""
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()

    with patch("app.config.exists", return_value=False), \
         patch("screens.setup.config.validate", return_value=[]), \
         patch("screens.setup.rclone.check_remote", return_value=False), \
         patch("screens.setup.config.write") as mock_write:
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            pilot.app.screen.query_one("#proton-drive", Input).value = str(proton)
            pilot.app.screen.query_one("#vault-root", Input).value = str(vault)
            pilot.app.screen.query_one("#remote-path", Input).value = "Photos/Bad-Path"
            pilot.app.screen.query_one("#save-btn", Button).press()
            await pilot.pause()  # worker starts
            await pilot.pause()  # _on_remote_check_done fires
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "not found" in errors.lower()
            assert not pilot.app.screen.query_one("#save-btn", Button).disabled
            mock_write.assert_not_called()
