"""
tests/test_inbox_screen.py

Integration tests for screens/inbox.py using Textual's Pilot harness.

All filesystem calls are tested via tmp_path; subprocess calls are mocked
where needed so tests run without rclone installed.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import ListView, Static

from app import KosCaptureApp
from screens.inbox import _format_size, _item_label, _scan_pdfs


# ── Pure helpers ───────────────────────────────────────────────────────────

def test_format_size_bytes():
    assert _format_size(512) == "512 B"


def test_format_size_kilobytes():
    assert _format_size(2048) == "2.0 KB"


def test_format_size_megabytes():
    assert _format_size(2 * 1_048_576) == "2.0 MB"


def test_scan_pdfs_returns_only_pdfs(tmp_path):
    (tmp_path / "note.pdf").write_bytes(b"%PDF")
    (tmp_path / "image.png").write_bytes(b"PNG")
    (tmp_path / "doc.PDF").write_bytes(b"%PDF")   # uppercase extension
    results = _scan_pdfs(tmp_path)
    names = {p.name for p in results}
    assert "note.pdf" in names
    assert "doc.PDF" in names
    assert "image.png" not in names


def test_scan_pdfs_newest_first(tmp_path):
    old = tmp_path / "old.pdf"; old.write_bytes(b"%PDF")
    new = tmp_path / "new.pdf"; new.write_bytes(b"%PDF")
    import os, time
    os.utime(old, (time.time() - 100, time.time() - 100))
    results = _scan_pdfs(tmp_path)
    assert results[0].name == "new.pdf"


def test_scan_pdfs_missing_folder():
    assert _scan_pdfs(Path("/nonexistent/path")) == []


def test_item_label_contains_filename_size_date(tmp_path):
    """_item_label() includes the filename, a size unit, and today's date."""
    from datetime import datetime
    pdf = tmp_path / "my-note.pdf"
    pdf.write_bytes(b"%PDF" * 256)  # 1024 bytes = 1.0 KB
    label = _item_label(pdf)
    assert "my-note.pdf" in label
    assert "KB" in label or "B" in label
    assert datetime.today().strftime("%Y-%m-%d") in label


# ── Screen integration ─────────────────────────────────────────────────────

async def _open_inbox(pilot):
    await pilot.app.push_screen("inbox")
    await pilot.pause()


async def test_inbox_renders_no_config():
    """Without config, shows error message instead of crashing."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_inbox(pilot)
            msg = str(pilot.app.screen.query_one("#message", Static).content)
            assert "setup" in msg.lower() or "config" in msg.lower()


async def test_inbox_renders_empty_folder(tmp_path):
    """Config exists but no PDFs in folder shows empty-state message."""
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()

    mock_cfg = MagicMock()
    mock_cfg.proton_drive = proton

    with patch("app.config.exists", return_value=True), \
         patch("screens.inbox.config.exists", return_value=True), \
         patch("screens.inbox.config.load", return_value=mock_cfg):
        async with KosCaptureApp().run_test() as pilot:
            await _open_inbox(pilot)
            msg = str(pilot.app.screen.query_one("#message", Static).content)
            assert "no pdf" in msg.lower()


async def test_inbox_lists_pdfs(tmp_path):
    """PDFs in folder populate the ListView."""
    proton = tmp_path / "proton"; proton.mkdir()
    (proton / "note.pdf").write_bytes(b"%PDF")
    (proton / "sketch.pdf").write_bytes(b"%PDF")
    vault = tmp_path / "vault"; vault.mkdir()

    mock_cfg = MagicMock()
    mock_cfg.proton_drive = proton

    with patch("app.config.exists", return_value=True), \
         patch("screens.inbox.config.exists", return_value=True), \
         patch("screens.inbox.config.load", return_value=mock_cfg):
        async with KosCaptureApp().run_test() as pilot:
            await _open_inbox(pilot)
            msg = str(pilot.app.screen.query_one("#message", Static).content)
            assert "2" in msg
            items = pilot.app.screen.query_one("#file-list", ListView)
            assert len(list(items.children)) == 2


async def test_inbox_message_shows_count(tmp_path):
    """Count in message matches number of PDFs found."""
    proton = tmp_path / "proton"; proton.mkdir()
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        (proton / name).write_bytes(b"%PDF")

    mock_cfg = MagicMock()
    mock_cfg.proton_drive = proton

    with patch("app.config.exists", return_value=True), \
         patch("screens.inbox.config.exists", return_value=True), \
         patch("screens.inbox.config.load", return_value=mock_cfg):
        async with KosCaptureApp().run_test() as pilot:
            await _open_inbox(pilot)
            msg = str(pilot.app.screen.query_one("#message", Static).content)
            assert "3" in msg


async def test_inbox_refresh_rescans(tmp_path):
    """Pressing r re-scans and updates the list."""
    proton = tmp_path / "proton"; proton.mkdir()
    mock_cfg = MagicMock()
    mock_cfg.proton_drive = proton

    with patch("app.config.exists", return_value=True), \
         patch("screens.inbox.config.exists", return_value=True), \
         patch("screens.inbox.config.load", return_value=mock_cfg):
        async with KosCaptureApp().run_test() as pilot:
            await _open_inbox(pilot)
            # Add a file after mount, then refresh
            (proton / "late.pdf").write_bytes(b"%PDF")
            await pilot.press("r")
            await pilot.pause()
            items = pilot.app.screen.query_one("#file-list", ListView)
            assert len(list(items.children)) == 1


async def test_inbox_escape_returns_home(tmp_path):
    """Escape switches back to the home screen."""
    with patch("app.config.exists", return_value=True), \
         patch("screens.inbox.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_inbox(pilot)
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "HomeScreen"


async def test_enter_on_file_pushes_wizard(tmp_path):
    """Selecting a PDF with Enter pushes WizardScreen with the file path."""
    proton = tmp_path / "proton"; proton.mkdir()
    (proton / "note.pdf").write_bytes(b"%PDF")

    mock_cfg = MagicMock()
    mock_cfg.proton_drive = proton

    with patch("app.config.exists", return_value=True), \
         patch("screens.inbox.config.exists", return_value=True), \
         patch("screens.inbox.config.load", return_value=mock_cfg):
        async with KosCaptureApp().run_test() as pilot:
            await _open_inbox(pilot)
            await pilot.press("enter")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "WizardScreen"
