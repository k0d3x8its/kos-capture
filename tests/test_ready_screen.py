"""
tests/test_ready_screen.py

Integration tests for screens/ready.py using Textual's Pilot harness.

ReadyScreen reads app.session_results directly — tests seed it before
pushing the screen and verify render + navigation behaviour.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import Button, RichLog, Static

from app import KosCaptureApp


async def _open_ready(pilot, results: list[Path]):
    pilot.app.session_results = list(results)
    await pilot.app.push_screen("ready")
    await pilot.pause()


# ── Render ──────────────────────────────────────────────────────────────────

async def test_ready_renders_with_results(tmp_path):
    """ReadyScreen composes without error when session_results is populated."""
    dest = tmp_path / "raw" / "Field-Logs" / "FL-vol-001" / "note.pdf"
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_ready(pilot, [dest])
            title = str(pilot.app.screen.query_one("#title", Static).content)
            assert "1" in title
            assert "File" in title


async def test_ready_plural_title(tmp_path):
    """Title says 'Files' (plural) when session_results has more than one entry."""
    paths = [tmp_path / f"file{i}.pdf" for i in range(3)]
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_ready(pilot, paths)
            title = str(pilot.app.screen.query_one("#title", Static).content)
            assert "3" in title
            assert "Files" in title


async def test_ready_shows_file_paths(tmp_path):
    """Each path in session_results is written to the RichLog."""
    dest = tmp_path / "raw" / "Field-Logs" / "FL-vol-001" / "note.pdf"
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_ready(pilot, [dest])
            log = pilot.app.screen.query_one("#file-log", RichLog)
            # RichLog.lines is the public sequence of rendered lines
            written = "\n".join(str(line) for line in log.lines)
            assert "note.pdf" in written


async def test_ready_shows_ingest_instruction():
    """The /kos-ingest command widget is present."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_ready(pilot, [Path("/some/file.pdf")])
            cmd = str(pilot.app.screen.query_one("#ingest-cmd", Static).content)
            assert "/kos-ingest" in cmd


# ── Navigation ───────────────────────────────────────────────────────────────

async def test_ready_done_button_goes_home_preserves_results(tmp_path):
    """Done button navigates to HomeScreen and preserves session_results.

    session_results persists across screens for the entire app run; clearing
    only happens on app restart (init in app.on_mount). This keeps View
    Summary reachable from Inbox even after the user has hit Done.
    """
    dest = tmp_path / "note.pdf"
    with patch("app.config.exists", return_value=True), \
         patch("screens.home.rclone.status") as mock_status, \
         patch("screens.home.config.exists", return_value=False):
        mock_status.return_value.installed = False
        mock_status.return_value.timer_active = False
        mock_status.return_value.last_sync = None
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_ready(pilot, [dest])
            pilot.app.screen.query_one("#done-btn", Button).press()
            await pilot.pause()
            assert pilot.app.session_results == [dest]
            assert pilot.app.screen.__class__.__name__ == "HomeScreen"


async def test_ready_escape_preserves_results_and_goes_home(tmp_path):
    """Escape goes back to HomeScreen WITHOUT clearing session_results."""
    dest = tmp_path / "note.pdf"
    with patch("app.config.exists", return_value=True), \
         patch("screens.home.rclone.status") as mock_status, \
         patch("screens.home.config.exists", return_value=False):
        mock_status.return_value.installed = False
        mock_status.return_value.timer_active = False
        mock_status.return_value.last_sync = None
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_ready(pilot, [dest])
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.session_results == [dest]
            assert pilot.app.screen.__class__.__name__ == "HomeScreen"


async def test_ready_empty_results_renders():
    """ReadyScreen handles an empty session_results list without crashing."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_ready(pilot, [])
            title = str(pilot.app.screen.query_one("#title", Static).content)
            assert "0" in title


async def test_ready_log_header_precedes_items(tmp_path):
    """Category headers always appear before their items in log.lines order.

    Validates data integrity of _populate_log — not scroll rendering, which
    is a Textual concern. If this passes and a visual glitch is seen, the
    bug is in Textual's RichLog rendering, not our code.
    """
    fl  = tmp_path / "raw" / "Field-Logs"    / "FL-vol-001" / "note.pdf"
    fr  = tmp_path / "raw" / "Field-Research" / "FR-vol-001" / "paper.pdf"
    yt  = tmp_path / "raw" / "transcripts"   / "youtube"    / "2024-01" / "video.md"
    pod = tmp_path / "raw" / "transcripts"   / "podcasts"   / "2024-01" / "ep.md"

    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_ready(pilot, [fl, fr, yt, pod])
            log = pilot.app.screen.query_one("#file-log", RichLog)
            lines = [str(line) for line in log.lines]

            def idx(needle: str) -> int:
                return next(i for i, l in enumerate(lines) if needle in l)

            fl_h  = idx("Field Logs")
            fr_h  = idx("Field Research")
            yt_h  = idx("YouTube")
            pod_h = idx("Podcasts")

            assert fl_h  < idx("note.pdf"),  "Field Logs header must precede its item"
            assert fr_h  < idx("paper.pdf"), "Field Research header must precede its item"
            assert yt_h  < idx("video.md"),  "YouTube header must precede its item"
            assert pod_h < idx("ep.md"),     "Podcasts header must precede its item"

            # Category ordering matches _CATEGORY_ORDER
            assert fl_h < fr_h < yt_h < pod_h


async def test_ready_on_show_reflects_new_results(tmp_path):
    """on_show re-populates log so results added after first visit appear."""
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_ready(pilot, [first])
            log = pilot.app.screen.query_one("#file-log", RichLog)
            written = "\n".join(str(line) for line in log.lines)
            assert "first.pdf" in written

            # Simulate returning to ReadyScreen after processing another file
            pilot.app.session_results.append(second)
            pilot.app.screen.on_show()
            await pilot.pause()

            log = pilot.app.screen.query_one("#file-log", RichLog)
            written = "\n".join(str(line) for line in log.lines)
            assert "first.pdf" in written
            assert "second.pdf" in written
            title = str(pilot.app.screen.query_one("#title", Static).content)
            assert "2" in title
