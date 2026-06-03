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


# --- _is_url() ---

def test_is_url_http():
    """_is_url() returns True for http:// URLs."""
    assert transcribe._is_url("http://example.com/ep.mp3") is True


def test_is_url_https():
    """_is_url() returns True for https:// URLs."""
    assert transcribe._is_url("https://www.youtube.com/watch?v=abc") is True


def test_is_url_ftp():
    """_is_url() returns True for ftp:// URLs."""
    assert transcribe._is_url("ftp://files.example.com/ep.mp3") is True


def test_is_url_local_path():
    """_is_url() returns False for absolute local paths."""
    assert transcribe._is_url("/home/user/recordings/ep.mp3") is False


def test_is_url_path_object():
    """_is_url() accepts Path objects and returns False for local paths."""
    assert transcribe._is_url(Path("/tmp/recording.mp4")) is False


def test_is_url_empty_string():
    """_is_url() returns False for an empty string."""
    assert transcribe._is_url("") is False


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


def test_write_md_no_frontmatter(tmp_path):
    """_write_md() output does not start with YAML frontmatter delimiters."""
    out = tmp_path / "out.md"
    transcribe._write_md([(0.0, "Hello")], "Any Title", out)
    assert not out.read_text().startswith("---")


# --- _transcribe_audio() — on_pct callback ---

def test_on_pct_called_per_segment(tmp_path):
    """on_pct is called once per segment with seg.end / total_duration."""
    audio = tmp_path / "recording.mp4"
    audio.write_bytes(b"fake")

    mock_info = MagicMock()
    mock_info.duration = 10.0

    seg1, seg2 = MagicMock(), MagicMock()
    seg1.start = 0.0;  seg1.end = 4.0;  seg1.text = " A "
    seg2.start = 4.0;  seg2.end = 9.0;  seg2.text = " B "

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([seg1, seg2], mock_info)

    pct_calls: list[float] = []
    with patch("core.transcribe.WhisperModel", return_value=mock_model):
        transcribe._transcribe_audio(audio, on_pct=pct_calls.append)

    assert len(pct_calls) == 2
    assert abs(pct_calls[0] - 0.4) < 0.01   # 4 / 10
    assert abs(pct_calls[1] - 0.9) < 0.01   # 9 / 10


def test_on_pct_not_called_when_duration_zero(tmp_path):
    """on_pct is never invoked when audio duration is 0 or unknown."""
    audio = tmp_path / "recording.mp4"
    audio.write_bytes(b"fake")

    mock_info = MagicMock()
    mock_info.duration = 0

    seg = MagicMock()
    seg.start = 0.0;  seg.end = 2.0;  seg.text = " A "

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([seg], mock_info)

    pct_calls: list[float] = []
    with patch("core.transcribe.WhisperModel", return_value=mock_model):
        transcribe._transcribe_audio(audio, on_pct=pct_calls.append)

    assert pct_calls == []


def test_on_pct_capped_at_one(tmp_path):
    """on_pct value is capped at 1.0 even if seg.end > total_duration."""
    audio = tmp_path / "recording.mp4"
    audio.write_bytes(b"fake")

    mock_info = MagicMock()
    mock_info.duration = 5.0

    seg = MagicMock()
    seg.start = 0.0;  seg.end = 6.0;  seg.text = " A "  # end > duration

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([seg], mock_info)

    pct_calls: list[float] = []
    with patch("core.transcribe.WhisperModel", return_value=mock_model):
        transcribe._transcribe_audio(audio, on_pct=pct_calls.append)

    assert pct_calls == [1.0]


# --- _download_audio() ---

def test_download_audio_missing_yt_dlp(tmp_path):
    """_download_audio() raises RuntimeError with a clear message when yt-dlp is absent."""
    # Setting sys.modules["yt_dlp"] = None causes `import yt_dlp` to raise ImportError,
    # simulating the package not being installed without actually uninstalling it.
    with patch.dict(sys.modules, {"yt_dlp": None}):
        with pytest.raises(RuntimeError, match="yt-dlp is required"):
            transcribe._download_audio("https://example.com", tmp_path)


def test_download_audio_progress_hook_registered(tmp_path):
    """_download_audio registers a yt-dlp progress hook and calls on_dl_pct correctly."""
    fake_wav = tmp_path / "audio.wav"
    fake_wav.write_bytes(b"fake")

    captured_hooks: list = []

    class FakeYDL:
        def __init__(self, opts):
            captured_hooks.extend(opts.get("progress_hooks", []))
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def extract_info(self, url, download):
            return {"title": "Test Title"}

    mock_yt_dlp = MagicMock()
    mock_yt_dlp.YoutubeDL = FakeYDL

    pct_calls: list[float] = []
    with patch.dict(sys.modules, {"yt_dlp": mock_yt_dlp}):
        transcribe._download_audio("https://example.com", tmp_path, on_dl_pct=pct_calls.append)

    assert len(captured_hooks) == 1
    hook = captured_hooks[0]

    hook({"status": "downloading", "downloaded_bytes": 300, "total_bytes": 1000})
    assert abs(pct_calls[0] - 0.3) < 0.01

    hook({"status": "finished"})
    assert pct_calls[-1] == 1.0


def test_download_audio_progress_hook_uses_estimate(tmp_path):
    """Hook falls back to total_bytes_estimate when total_bytes is absent."""
    fake_wav = tmp_path / "audio.wav"
    fake_wav.write_bytes(b"fake")

    captured_hooks: list = []

    class FakeYDL:
        def __init__(self, opts):
            captured_hooks.extend(opts.get("progress_hooks", []))
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def extract_info(self, url, download):
            return {"title": "T"}

    mock_yt_dlp = MagicMock()
    mock_yt_dlp.YoutubeDL = FakeYDL

    pct_calls: list[float] = []
    with patch.dict(sys.modules, {"yt_dlp": mock_yt_dlp}):
        transcribe._download_audio("https://example.com", tmp_path, on_dl_pct=pct_calls.append)

    hook = captured_hooks[0]
    hook({"status": "downloading", "downloaded_bytes": 500, "total_bytes_estimate": 1000})
    assert abs(pct_calls[0] - 0.5) < 0.01


def test_download_audio_no_pct_when_total_unknown(tmp_path):
    """Hook does not call on_dl_pct when total size is unknown."""
    fake_wav = tmp_path / "audio.wav"
    fake_wav.write_bytes(b"fake")

    captured_hooks: list = []

    class FakeYDL:
        def __init__(self, opts):
            captured_hooks.extend(opts.get("progress_hooks", []))
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def extract_info(self, url, download):
            return {"title": "T"}

    mock_yt_dlp = MagicMock()
    mock_yt_dlp.YoutubeDL = FakeYDL

    pct_calls: list[float] = []
    with patch.dict(sys.modules, {"yt_dlp": mock_yt_dlp}):
        transcribe._download_audio("https://example.com", tmp_path, on_dl_pct=pct_calls.append)

    hook = captured_hooks[0]
    hook({"status": "downloading", "downloaded_bytes": 500})  # no total
    assert pct_calls == []


def test_download_audio_sponsorblock_set_for_youtube(tmp_path):
    """SponsorBlock opts are injected when source_type is 'youtube'."""
    fake_wav = tmp_path / "audio.wav"
    fake_wav.write_bytes(b"fake")

    captured_opts: list[dict] = []

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.append(opts)
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def extract_info(self, url, download):
            return {"title": "T"}

    mock_yt_dlp = MagicMock()
    mock_yt_dlp.YoutubeDL = FakeYDL

    with patch.dict(sys.modules, {"yt_dlp": mock_yt_dlp}):
        transcribe._download_audio("https://example.com", tmp_path, source_type="youtube")

    opts = captured_opts[0]
    assert opts.get("sponsorblock_remove") == ["sponsor", "selfpromo", "interaction"]


def test_download_audio_sponsorblock_absent_for_podcasts(tmp_path):
    """SponsorBlock opts are NOT injected for non-YouTube source types."""
    fake_wav = tmp_path / "audio.wav"
    fake_wav.write_bytes(b"fake")

    captured_opts: list[dict] = []

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.append(opts)
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def extract_info(self, url, download):
            return {"title": "T"}

    mock_yt_dlp = MagicMock()
    mock_yt_dlp.YoutubeDL = FakeYDL

    with patch.dict(sys.modules, {"yt_dlp": mock_yt_dlp}):
        transcribe._download_audio("https://example.com", tmp_path, source_type="podcasts")

    assert "sponsorblock_remove" not in captured_opts[0]


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
    assert out.name == f"my-meeting-{date.today().isoformat()}.md"

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


# --- run() — youtube path ---

def test_run_youtube_writes_md(tmp_path):
    """run() for youtube downloads audio and writes a dated .md file."""
    transcript_dir = tmp_path / "raw" / "transcripts" / "youtube"
    fake_wav = tmp_path / "video.wav"
    fake_wav.write_bytes(b"fake")

    mock_segment = MagicMock()
    mock_segment.start = 0.0
    mock_segment.text = " YouTube segment "
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())

    with patch("core.transcribe._download_audio", return_value=(fake_wav, "my video")), \
         patch("core.transcribe.WhisperModel", return_value=mock_model):
        out = transcribe.run("youtube", "https://example.com", transcript_dir, "my video")

    assert out.exists()
    assert "my-video" in out.name
    content = out.read_text()
    assert "# my video" in content
    assert "[00:00] YouTube segment" in content


def test_run_youtube_creates_transcript_dir(tmp_path):
    """run() for youtube creates the transcript directory if it doesn't exist."""
    transcript_dir = tmp_path / "raw" / "transcripts" / "youtube"
    fake_wav = tmp_path / "video.wav"
    fake_wav.write_bytes(b"fake")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock())

    with patch("core.transcribe._download_audio", return_value=(fake_wav, "title")), \
         patch("core.transcribe.WhisperModel", return_value=mock_model):
        transcribe.run("youtube", "https://example.com", transcript_dir, "title")

    assert transcript_dir.exists()


# --- run() — podcasts path ---

def test_run_podcasts_writes_md(tmp_path):
    """run() for podcasts follows the same download+transcribe path as youtube."""
    transcript_dir = tmp_path / "raw" / "transcripts" / "podcasts"
    fake_wav = tmp_path / "episode.wav"
    fake_wav.write_bytes(b"fake")

    mock_segment = MagicMock()
    mock_segment.start = 60.0
    mock_segment.text = " Podcast segment "
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())

    with patch("core.transcribe._download_audio", return_value=(fake_wav, "my podcast")), \
         patch("core.transcribe.WhisperModel", return_value=mock_model):
        out = transcribe.run("podcasts", "https://example.com/feed.rss", transcript_dir, "my podcast")

    assert out.exists()
    assert "my-podcast" in out.name
    content = out.read_text()
    assert "# my podcast" in content
    assert "[01:00] Podcast segment" in content
