"""
tests/test_transcribe_screen.py

Integration tests for screens/transcribe.py using Textual's Pilot harness.

Strategy mirrors test_sync_screen.py: push the screen, mock heavy operations,
and call completion handlers directly to avoid waiting on real threads.
core.transcribe.run is always mocked — no faster-whisper or yt-dlp in tests.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import Button, ContentSwitcher, Input, ProgressBar, RichLog, Static

from app import KosCaptureApp


def _make_cfg(vault_root: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.vault_root = vault_root
    return cfg


async def _open_transcribe(pilot):
    await pilot.app.push_screen("transcribe")
    await pilot.pause()


async def _select_source(pilot, index: int):
    """Select source type by index (0=meetings, 1=youtube, 2=podcasts)."""
    for _ in range(index):
        await pilot.press("down")
    await pilot.press("enter")
    await pilot.pause()


# ── Render ──────────────────────────────────────────────────────────────────

async def test_transcribe_renders():
    """TranscribeScreen composes without error and shows key widgets."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            assert pilot.app.screen.query_one("#source-list") is not None
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-source"


async def test_transcribe_starts_on_source_step():
    """Screen opens on step-source."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            label = str(pilot.app.screen.query_one("#step-label", Static).content)
            assert "1 of 2" in label
            assert "source" in label.lower()


# ── Source selection → input step ────────────────────────────────────────────

async def test_select_meetings_advances_to_input():
    """Selecting Proton Meet switches to the input step."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 0)
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-input"
            assert pilot.app.screen._source_type == "meetings"


async def test_select_youtube_advances_to_input():
    """Selecting YouTube switches to the input step."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 1)
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-input"
            assert pilot.app.screen._source_type == "youtube"


async def test_select_podcasts_advances_to_input():
    """Selecting Podcast switches to the input step."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 2)
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-input"
            assert pilot.app.screen._source_type == "podcasts"


async def test_source_placeholder_changes_per_type():
    """#source-input placeholder reflects the selected source type."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 1)  # YouTube
            ph = pilot.app.screen.query_one("#source-input", Input).placeholder
            assert "youtube" in ph.lower() or "http" in ph.lower()


async def test_title_placeholder_changes_per_type():
    """#title-input placeholder reflects auto-detect behaviour for the source type."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 0)  # meetings
            ph = pilot.app.screen.query_one("#title-input", Input).placeholder
            assert "auto" in ph.lower() or "filename" in ph.lower()


# ── Validation errors ────────────────────────────────────────────────────────

async def test_empty_source_shows_error():
    """Begin with blank source shows a required-field error."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 1)  # YouTube
            pilot.app.screen.query_one("#begin-btn", Button).press()
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "required" in errors.lower()


async def test_meetings_nonexistent_file_shows_error():
    """Begin with a meetings source path that doesn't exist shows file-not-found error."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 0)  # meetings
            pilot.app.screen.query_one("#source-input", Input).value = "/does/not/exist.mp4"
            pilot.app.screen.query_one("#begin-btn", Button).press()
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "not found" in errors.lower()


async def test_podcast_local_nonexistent_file_shows_error(tmp_path):
    """Podcast with a local path that doesn't exist shows file-not-found error."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 2)  # podcasts
            pilot.app.screen.query_one("#source-input", Input).value = "/missing/episode.mp3"
            pilot.app.screen.query_one("#begin-btn", Button).press()
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "not found" in errors.lower()


async def test_podcast_url_skips_local_file_check():
    """Podcast with an http URL does not trigger a local-file-exists check."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 2)  # podcasts
            pilot.app.screen.query_one("#source-input", Input).value = "https://example.com/ep.mp3"
            pilot.app.screen.query_one("#begin-btn", Button).press()
            await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            # Should fail on no-config, not file-not-found
            assert "config" in errors.lower()


async def test_no_config_shows_error(tmp_path):
    """Begin with no config file shows config error (not a crash)."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 1)  # YouTube (no local-file check)
            with patch("screens.transcribe.config.exists", return_value=False):
                pilot.app.screen.query_one("#source-input", Input).value = "https://youtube.com/watch?v=abc"
                pilot.app.screen.query_one("#begin-btn", Button).press()
                await pilot.pause()
            errors = str(pilot.app.screen.query_one("#errors", Static).content)
            assert "config" in errors.lower()


# ── Navigation ───────────────────────────────────────────────────────────────

async def test_escape_on_source_step_goes_home():
    """Escape on step 1 switches to HomeScreen."""
    with patch("app.config.exists", return_value=True), \
         patch("screens.home.rclone.status") as mock_status, \
         patch("screens.home.config.exists", return_value=False):
        mock_status.return_value.installed = False
        mock_status.return_value.timer_active = False
        mock_status.return_value.last_sync = None
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_transcribe(pilot)
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "HomeScreen"


async def test_escape_on_input_step_returns_to_source():
    """Escape on step 2 returns to step-source."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 0)
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-input"
            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-source"


async def test_escape_blocked_during_transcription():
    """Escape while transcription is running shows a warning and stays on the screen."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            screen = pilot.app.screen
            screen._transcribing = True
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen is screen
            errors = str(screen.query_one("#errors", Static).content)
            assert "progress" in errors.lower() or "wait" in errors.lower()


async def test_on_show_resets_to_source_step():
    """on_show resets the screen to step-source when not running."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            await _select_source(pilot, 0)
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-input"
            # Simulate re-entry via on_show
            pilot.app.screen.on_show()
            await pilot.pause()
            await pilot.pause()
            assert pilot.app.screen.query_one(ContentSwitcher).current == "step-source"


async def test_on_show_does_not_reset_while_transcribing():
    """on_show does not reset to step-source while transcription is in progress."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            screen = pilot.app.screen
            screen._transcribing = True
            screen._go_to("step-running")
            screen.on_show()
            await pilot.pause()
            assert screen.query_one(ContentSwitcher).current == "step-running"


# ── Completion callbacks ──────────────────────────────────────────────────────

async def test_transcription_done_appends_session_results(tmp_path):
    """_on_transcription_done appends the output path to app.session_results."""
    out = tmp_path / "2026-01-01-My-Talk.md"
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            screen = pilot.app.screen
            screen._transcribing = True
            screen._on_transcription_done(out)
            await pilot.pause()
            assert out in pilot.app.session_results


async def test_transcription_done_switches_to_ready(tmp_path):
    """_on_transcription_done navigates to ReadyScreen."""
    out = tmp_path / "transcript.md"
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            screen = pilot.app.screen
            screen._transcribing = True
            screen._on_transcription_done(out)
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "ReadyScreen"


async def test_transcription_error_shows_message_and_clears_transcribing():
    """_on_transcription_error writes to the log and clears _transcribing."""
    with patch("app.config.exists", return_value=False):
        async with KosCaptureApp().run_test() as pilot:
            await _open_transcribe(pilot)
            screen = pilot.app.screen
            screen._transcribing = True
            screen._go_to("step-running")
            screen._on_transcription_error("yt-dlp not installed")
            await pilot.pause()
            assert screen._transcribing is False
            log = screen.query_one("#run-log", RichLog)
            written = "\n".join(str(line) for line in log.lines)
            assert "yt-dlp" in written or "error" in written.lower()


async def test_worker_success_path(tmp_path):
    """Full Begin → worker → done path appends result and navigates to Ready."""
    mp4 = tmp_path / "recording.mp4"
    mp4.write_bytes(b"\x00" * 16)
    out = tmp_path / "2026-01-01-recording.md"
    cfg = _make_cfg(tmp_path)

    with patch("app.config.exists", return_value=True), \
         patch("screens.transcribe.config.exists", return_value=True), \
         patch("screens.transcribe.config.load", return_value=cfg), \
         patch("screens.transcribe.transcribe.run", return_value=out):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_transcribe(pilot)
            await _select_source(pilot, 0)  # meetings
            pilot.app.screen.query_one("#source-input", Input).value = str(mp4)
            pilot.app.screen.query_one("#begin-btn", Button).press()
            await pilot.pause()
            await pilot.pause()
            assert out in pilot.app.session_results
            assert pilot.app.screen.__class__.__name__ == "ReadyScreen"


async def test_worker_with_custom_title(tmp_path):
    """Custom title is passed to transcribe.run when provided."""
    mp4 = tmp_path / "recording.mp4"
    mp4.write_bytes(b"\x00" * 16)
    out = tmp_path / "2026-01-01-My-Custom-Title.md"
    cfg = _make_cfg(tmp_path)

    with patch("app.config.exists", return_value=True), \
         patch("screens.transcribe.config.exists", return_value=True), \
         patch("screens.transcribe.config.load", return_value=cfg), \
         patch("screens.transcribe.transcribe.run", return_value=out) as mock_run:
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_transcribe(pilot)
            await _select_source(pilot, 0)
            pilot.app.screen.query_one("#source-input", Input).value = str(mp4)
            pilot.app.screen.query_one("#title-input", Input).value = "My Custom Title"
            pilot.app.screen.query_one("#begin-btn", Button).press()
            await pilot.pause()
            await pilot.pause()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("title") == "My Custom Title"


async def test_worker_blank_title_passes_none(tmp_path):
    """Blank title field passes title=None to transcribe.run (triggers auto-detect)."""
    mp4 = tmp_path / "recording.mp4"
    mp4.write_bytes(b"\x00" * 16)
    out = tmp_path / "2026-01-01-recording.md"
    cfg = _make_cfg(tmp_path)

    with patch("app.config.exists", return_value=True), \
         patch("screens.transcribe.config.exists", return_value=True), \
         patch("screens.transcribe.config.load", return_value=cfg), \
         patch("screens.transcribe.transcribe.run", return_value=out) as mock_run:
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_transcribe(pilot)
            await _select_source(pilot, 0)
            pilot.app.screen.query_one("#source-input", Input).value = str(mp4)
            pilot.app.screen.query_one("#title-input", Input).value = ""
            pilot.app.screen.query_one("#begin-btn", Button).press()
            await pilot.pause()
            await pilot.pause()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("title") is None


# ── Download progress bar visibility ─────────────────────────────────────────

async def test_download_bar_visible_for_youtube(tmp_path):
    """Download ProgressBar is shown when source is YouTube (URL)."""
    out = tmp_path / "video.md"
    cfg = _make_cfg(tmp_path)

    with patch("app.config.exists", return_value=True), \
         patch("screens.transcribe.config.exists", return_value=True), \
         patch("screens.transcribe.config.load", return_value=cfg), \
         patch("screens.transcribe.transcribe.run", return_value=out):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_transcribe(pilot)
            await _select_source(pilot, 1)  # YouTube
            screen = pilot.app.screen
            screen.query_one("#source-input", Input).value = "https://youtube.com/watch?v=abc"
            with patch.object(screen, "_on_transcription_done"):
                screen._begin()
                assert screen.query_one("#run-dl-progress", ProgressBar).display is True
                await pilot.pause()


async def test_download_bar_hidden_for_meetings(tmp_path):
    """Download ProgressBar is hidden for local file sources (meetings)."""
    mp4 = tmp_path / "recording.mp4"
    mp4.write_bytes(b"\x00" * 16)
    out = tmp_path / "recording.md"
    cfg = _make_cfg(tmp_path)

    with patch("app.config.exists", return_value=True), \
         patch("screens.transcribe.config.exists", return_value=True), \
         patch("screens.transcribe.config.load", return_value=cfg), \
         patch("screens.transcribe.transcribe.run", return_value=out):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_transcribe(pilot)
            await _select_source(pilot, 0)  # meetings
            screen = pilot.app.screen
            screen.query_one("#source-input", Input).value = str(mp4)
            with patch.object(screen, "_on_transcription_done"):
                screen._begin()
                assert screen.query_one("#run-dl-progress", ProgressBar).display is False
                await pilot.pause()


async def test_download_bar_visible_for_podcast_url(tmp_path):
    """Download ProgressBar is shown for podcast with an http URL."""
    out = tmp_path / "episode.md"
    cfg = _make_cfg(tmp_path)

    with patch("app.config.exists", return_value=True), \
         patch("screens.transcribe.config.exists", return_value=True), \
         patch("screens.transcribe.config.load", return_value=cfg), \
         patch("screens.transcribe.transcribe.run", return_value=out):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_transcribe(pilot)
            await _select_source(pilot, 2)  # podcasts
            screen = pilot.app.screen
            screen.query_one("#source-input", Input).value = "https://example.com/ep.mp3"
            with patch.object(screen, "_on_transcription_done"):
                screen._begin()
                assert screen.query_one("#run-dl-progress", ProgressBar).display is True
                await pilot.pause()


async def test_download_bar_hidden_for_podcast_local(tmp_path):
    """Download ProgressBar is hidden for podcast with a local file path."""
    mp3 = tmp_path / "episode.mp3"
    mp3.write_bytes(b"\x00" * 16)
    out = tmp_path / "episode.md"
    cfg = _make_cfg(tmp_path)

    with patch("app.config.exists", return_value=True), \
         patch("screens.transcribe.config.exists", return_value=True), \
         patch("screens.transcribe.config.load", return_value=cfg), \
         patch("screens.transcribe.transcribe.run", return_value=out):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await _open_transcribe(pilot)
            await _select_source(pilot, 2)  # podcasts
            screen = pilot.app.screen
            screen.query_one("#source-input", Input).value = str(mp3)
            with patch.object(screen, "_on_transcription_done"):
                screen._begin()
                assert screen.query_one("#run-dl-progress", ProgressBar).display is False
                await pilot.pause()
