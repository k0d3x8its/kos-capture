"""
tests/test_transcribe.py

Unit tests for core/transcribe.py.

faster-whisper model loading is mocked in all tests that call transcription
functions — no model weights are downloaded and no audio is actually processed.
yt-dlp is also mocked or its absence simulated via sys.modules manipulation.

Tests for run() with youtube/podcasts source types are not included here
because they require a real network download and a real audio file. Those
paths are covered by manual end-to-end testing.
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import core.transcribe as transcribe


# --- _fmt_time() ---

def test_fmt_time_zero():
    """_fmt_time(0) produces [00:00]."""
    assert transcribe._fmt_time(0) == "[00:00]"


def test_fmt_time_seconds():
    """_fmt_time handles sub-minute values correctly."""
    assert transcribe._fmt_time(45) == "[00:45]"


def test_fmt_time_one_minute():
    """_fmt_time converts 90 seconds to [01:30]."""
    assert transcribe._fmt_time(90) == "[01:30]"


def test_fmt_time_large():
    """_fmt_time keeps minutes as total minutes — no hours field."""
    assert transcribe._fmt_time(3661) == "[61:01]"


# --- _write_md() ---

def test_write_md_heading(tmp_path):
    """_write_md() writes the title as a markdown h1 heading."""
    out = tmp_path / "out.md"
    transcribe._write_md([], "My Title", out)
    assert "# My Title" in out.read_text()


def test_write_md_segments(tmp_path):
    """_write_md() writes each segment with its [MM:SS] timestamp."""
    out = tmp_path / "out.md"
    transcribe._write_md([(0.0, "Hello"), (90.0, "World")], "Title", out)
    content = out.read_text()
    assert "[00:00] Hello" in content
    assert "[01:30] World" in content


# --- _download_audio() ---

def test_download_audio_missing_yt_dlp(tmp_path):
    """_download_audio() raises RuntimeError with a clear message when yt-dlp is absent."""
    # Setting sys.modules["yt_dlp"] = None causes `import yt_dlp` to raise ImportError,
    # simulating the package not being installed without actually uninstalling it.
    with patch.dict(sys.modules, {"yt_dlp": None}):
        with pytest.raises(RuntimeError, match="yt-dlp is required"):
            transcribe._download_audio("https://example.com", tmp_path)


# --- run() — meetings path ---

def test_run_meetings_writes_md(tmp_path):
    """run() for meetings writes a dated .md file with timestamped segments."""
    audio = tmp_path / "recording.mp4"
    audio.write_bytes(b"fake")  # faster-whisper is mocked — file content doesn't matter
    transcript_dir = tmp_path / "raw" / "transcripts" / "meetings"

    # Build a mock WhisperModel that returns one segment
    mock_segment = MagicMock()
    mock_segment.start = 0.0
    mock_segment.text = " Test segment "  # leading/trailing space — should be stripped
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())

    with patch("core.transcribe.WhisperModel", return_value=mock_model):
        out = transcribe.run("meetings", audio, transcript_dir, "my meeting")

    # Filename: spaces in title replaced with hyphens
    assert out.exists()
    assert out.name == f"{date.today().isoformat()}-my-meeting.md"

    content = out.read_text()
    assert "# my meeting" in content
    assert "[00:00] Test segment" in content  # strip() removed the surrounding spaces


def test_run_meetings_creates_transcript_dir(tmp_path):
    """run() creates the transcript directory if it doesn't exist yet."""
    audio = tmp_path / "recording.mp4"
    audio.write_bytes(b"fake")
    transcript_dir = tmp_path / "raw" / "transcripts" / "meetings"

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock())

    with patch("core.transcribe.WhisperModel", return_value=mock_model):
        transcribe.run("meetings", audio, transcript_dir, "title")

    assert transcript_dir.exists()
