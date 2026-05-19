"""
tests/test_wizard_screen.py

Integration tests for screens/wizard.py using Textual's Pilot harness.

Strategy: push WizardScreen(pdf_path) as an instance (not a string key)
since the constructor requires a file_path argument. Tests walk each step
via ListView.Selected and Button.press().
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from textual.widgets import Button, ContentSwitcher, Input, Static

from app import KosCaptureApp
from screens.wizard import WizardScreen, _SUFFIXES, _NEW_VOLUME_LABEL


def _make_cfg(vault_root: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.vault_root = vault_root
    return cfg


async def _open_wizard(pilot, pdf: Path, vault_root: Path):
    with patch("screens.wizard.config.exists", return_value=True), \
         patch("screens.wizard.config.load", return_value=_make_cfg(vault_root)):
        await pilot.app.push_screen(WizardScreen(pdf))
        await pilot.pause()


# ── Render ──────────────────────────────────────────────────────────────────

async def test_wizard_renders(tmp_path):
    """Wizard composes without errors and shows the filename."""
    pdf = tmp_path / "scan-2024.pdf"
    pdf.touch()
    vault = tmp_path / "vault"

    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault)
            title = str(pilot.app.screen.query_one("#filename", Static).content)
            assert "scan-2024.pdf" in title


async def test_wizard_starts_on_suffix_step(tmp_path):
    """Wizard opens on the suffix step (ContentSwitcher shows step-suffix)."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault = tmp_path / "vault"

    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault)
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-suffix"


# ── Step 1: suffix ───────────────────────────────────────────────────────────

async def test_suffix_selection_advances_to_collection(tmp_path):
    """Selecting a suffix item switches to the collection step."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault = tmp_path / "vault"

    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault)
            # Press Enter on the first suffix item (bare)
            await pilot.press("enter")
            await pilot.pause()
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-collection"


async def test_suffix_bare_stores_empty_string(tmp_path):
    """Selecting 'bare' stores an empty suffix."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault = tmp_path / "vault"

    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault)
            await pilot.press("enter")  # bare = index 0
            await pilot.pause()
            assert pilot.app.screen._suffix == ""


async def test_suffix_sticky_stores_correct_value(tmp_path):
    """Selecting '-sticky' stores '-sticky' as the suffix."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault = tmp_path / "vault"

    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault)
            await pilot.press("down")   # move to -sticky (index 1)
            await pilot.press("enter")
            await pilot.pause()
            assert pilot.app.screen._suffix == "-sticky"


# ── Step 2: collection ───────────────────────────────────────────────────────

async def test_collection_selection_advances_to_volume(tmp_path):
    """Selecting a collection switches to the volume step."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault = tmp_path / "vault"

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=[]):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault)
            await pilot.press("enter")  # suffix
            await pilot.pause()
            await pilot.press("enter")  # collection (Field-Logs)
            await pilot.pause()
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-volume"
            assert pilot.app.screen._collection == "Field-Logs"


# ── Step 3: volume ───────────────────────────────────────────────────────────

async def test_volume_list_shows_existing_volumes(tmp_path):
    """Volume step shows existing vault volumes before the New option."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=["FL-vol-001", "FL-vol-002"]):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")  # suffix
            await pilot.pause()
            await pilot.press("enter")  # collection
            await pilot.pause()
            volume_items = pilot.app.screen._volume_items
            assert "FL-vol-001" in volume_items
            assert "FL-vol-002" in volume_items
            assert _NEW_VOLUME_LABEL in volume_items


async def test_existing_volume_selection_advances_to_confirm(tmp_path):
    """Selecting an existing volume switches to the confirm step."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=["FL-vol-001"]), \
         patch("screens.wizard.vault.volume_path", return_value=tmp_path / "dest"):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")  # suffix
            await pilot.pause()
            await pilot.press("enter")  # collection
            await pilot.pause()
            await pilot.press("enter")  # volume (FL-vol-001)
            await pilot.pause()
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-confirm"
            assert pilot.app.screen._volume == "FL-vol-001"


async def test_new_volume_option_advances_to_new_volume_step(tmp_path):
    """Selecting '+ New volume' switches to the new-volume input step."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=[]):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")  # suffix
            await pilot.pause()
            await pilot.press("enter")  # collection
            await pilot.pause()
            # Only item is "+ New volume"
            await pilot.press("enter")
            await pilot.pause()
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-new-volume"


# ── Step 3b: new volume ──────────────────────────────────────────────────────

async def test_new_volume_empty_name_shows_error(tmp_path):
    """Submitting an empty volume name shows a required-field error."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=[]):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")  # suffix
            await pilot.pause()
            await pilot.press("enter")  # collection
            await pilot.pause()
            await pilot.press("enter")  # new volume
            await pilot.pause()
            pilot.app.screen.query_one("#new-vol-btn", Button).press()
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "required" in errors.lower()


async def test_new_volume_invalid_name_shows_error(tmp_path):
    """Volume name containing / or .. shows a validation error."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=[]):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            pilot.app.screen.query_one("#new-vol-input", Input).value = "bad/name"
            pilot.app.screen.query_one("#new-vol-btn", Button).press()
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "/" in errors or "must not" in errors.lower()


async def test_new_volume_valid_name_advances_to_confirm(tmp_path):
    """Valid new volume name creates the directory and advances to confirm."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=[]), \
         patch("screens.wizard.vault.create_volume") as mock_create, \
         patch("screens.wizard.vault.volume_path", return_value=tmp_path / "dest"):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")  # suffix
            await pilot.pause()
            await pilot.press("enter")  # collection
            await pilot.pause()
            await pilot.press("enter")  # new volume option
            await pilot.pause()
            pilot.app.screen.query_one("#new-vol-input", Input).value = "FL-vol-003"
            pilot.app.screen.query_one("#new-vol-btn", Button).press()
            await pilot.pause()
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-confirm"
            assert pilot.app.screen._volume == "FL-vol-003"
            mock_create.assert_called_once()


# ── Step 4: confirm ──────────────────────────────────────────────────────────

async def test_confirm_dest_path_shown(tmp_path):
    """Confirm step shows the destination path including the new filename."""
    pdf = tmp_path / "scan-2024.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"
    dest_dir = tmp_path / "dest"

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=["FL-vol-001"]), \
         patch("screens.wizard.vault.volume_path", return_value=dest_dir):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")  # suffix (bare)
            await pilot.pause()
            await pilot.press("enter")  # collection
            await pilot.pause()
            await pilot.press("enter")  # volume
            await pilot.pause()
            dest_text = str(pilot.app.screen.query_one("#dest-path", Static).content)
            assert "scan-2024.pdf" in dest_text


async def test_confirm_move_calls_shutil_move(tmp_path):
    """Clicking 'Move file →' calls shutil.move with correct source and dest."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"
    dest_dir = tmp_path / "dest"; dest_dir.mkdir()

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=["FL-vol-001"]), \
         patch("screens.wizard.vault.volume_path", return_value=dest_dir), \
         patch("screens.wizard.shutil.move") as mock_move:
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")  # suffix
            await pilot.pause()
            await pilot.press("enter")  # collection
            await pilot.pause()
            await pilot.press("enter")  # volume
            await pilot.pause()
            pilot.app.screen.query_one("#confirm-btn", Button).press()
            await pilot.pause()
            mock_move.assert_called_once()
            src, dst = mock_move.call_args[0]
            assert src == str(pdf)
            assert dst.endswith("scan.pdf")


async def test_confirm_move_appends_to_session_results(tmp_path):
    """After a successful move, dest path is in app.session_results."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"
    dest_dir = tmp_path / "dest"; dest_dir.mkdir()

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=["FL-vol-001"]), \
         patch("screens.wizard.vault.volume_path", return_value=dest_dir), \
         patch("screens.wizard.shutil.move"):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")  # suffix
            await pilot.pause()
            await pilot.press("enter")  # collection
            await pilot.pause()
            await pilot.press("enter")  # volume
            await pilot.pause()
            pilot.app.screen.query_one("#confirm-btn", Button).press()
            await pilot.pause()
            assert len(pilot.app.session_results) == 1
            assert "scan.pdf" in pilot.app.session_results[0].name


async def test_confirm_move_pops_screen(tmp_path):
    """After a successful move, WizardScreen is popped (Inbox is shown)."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"
    dest_dir = tmp_path / "dest"; dest_dir.mkdir()

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=["FL-vol-001"]), \
         patch("screens.wizard.vault.volume_path", return_value=dest_dir), \
         patch("screens.wizard.shutil.move"), \
         patch("screens.inbox.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await pilot.app.push_screen("inbox")
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            pilot.app.screen.query_one("#confirm-btn", Button).press()
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "InboxScreen"


# ── Escape navigation ────────────────────────────────────────────────────────

async def test_escape_on_first_step_pops_to_previous_screen(tmp_path):
    """Pressing Escape on the suffix step pops WizardScreen."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"

    with patch("app.config.exists", return_value=False), \
         patch("screens.inbox.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await pilot.app.push_screen("inbox")
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "InboxScreen"


async def test_escape_on_collection_step_returns_to_suffix(tmp_path):
    """Pressing Escape on the collection step returns to suffix."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"

    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")  # advance to collection
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-suffix"


async def test_escape_on_volume_step_returns_to_collection(tmp_path):
    """Pressing Escape on the volume step returns to collection."""
    pdf = tmp_path / "scan.pdf"; pdf.touch()
    vault_root = tmp_path / "vault"

    with patch("app.config.exists", return_value=False), \
         patch("screens.wizard.vault.volumes", return_value=[]):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_wizard(pilot, pdf, vault_root)
            await pilot.press("enter")  # suffix
            await pilot.pause()
            await pilot.press("enter")  # collection
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-collection"
