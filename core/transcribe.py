"""
core/transcribe.py

Local transcription engine wrapping faster-whisper and yt-dlp.

Handles three source types:
    - meetings:  local MP4 file (from Proton Meet)
    - youtube:   YouTube URL  → yt-dlp downloads audio → faster-whisper
    - podcasts:  podcast URL or RSS → yt-dlp downloads audio → faster-whisper

All transcription runs locally on CPU (int8 quantisation). No audio or
transcript data is sent to any external service.

Output format:
    raw/transcripts/<source_type>/YYYY-MM-DD-<title>.md

Each .md file contains a heading followed by one line per segment:
    # <title>
    [MM:SS] segment text
    [MM:SS] segment text
    ...

yt-dlp is imported lazily inside _download_audio() so the app starts
normally even if yt-dlp is not installed — the ImportError only surfaces
when the user actually attempts a YouTube or Podcast transcription.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from faster_whisper import WhisperModel

# Valid values for the source_type argument throughout this module.
SOURCE_TYPES = ["meetings", "youtube", "podcasts"]


def _fmt_time(seconds: float) -> str:
    """
    Convert a float number of seconds to a [MM:SS] timestamp string.

    faster-whisper returns segment start times as floats. This format matches
    the KOS transcript convention used by /kos-ingest when parsing .md files.

    Examples:
        _fmt_time(0)    → '[00:00]'
        _fmt_time(90)   → '[01:30]'
        _fmt_time(3661) → '[61:01]'  (no hours — stays as total minutes)
    """
    m, s = divmod(int(seconds), 60)
    return f"[{m:02d}:{s:02d}]"


def _download_audio(url: str, tmp_dir: Path) -> tuple[Path, str]:
    """
    Download audio from a URL using yt-dlp and return (audio_path, title).

    Audio is extracted to WAV format via FFmpegExtractAudio post-processor
    so faster-whisper can read it directly without additional conversion.
    Files are written to tmp_dir, which is a TemporaryDirectory managed by
    the caller — cleanup is automatic when the context manager exits.

    Raises RuntimeError if yt-dlp is not installed (ImportError caught here
    and re-raised with a user-friendly message so the Transcribe screen can
    display it cleanly).

    quiet=True and no_warnings=True suppress yt-dlp's stdout chatter since
    progress is handled at the screen level, not here.
    """
    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError("yt-dlp is required for YouTube and Podcast transcription")

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(tmp_dir / "%(title)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "audio")

    # yt-dlp writes the extracted audio with a .wav extension after post-processing.
    matches = list(tmp_dir.glob("*.wav"))
    if not matches:
        raise RuntimeError(f"yt-dlp download produced no audio file for: {url}")
    return matches[0], title


def _transcribe_audio(audio_path: Path, model_size: str = "base") -> list[tuple[float, str]]:
    """
    Run faster-whisper on an audio file and return a list of (start, text) tuples.

    Model is loaded fresh each call — acceptable for a TUI where transcription
    is a user-triggered one-shot operation, not a batch pipeline.

    device="cpu" and compute_type="int8" keeps memory usage low and removes
    the GPU requirement. 'base' model is the default — good accuracy/speed
    tradeoff for Field Notes and meeting audio.

    Segments are stripped of leading/trailing whitespace because faster-whisper
    sometimes includes a leading space in segment text.
    """
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path))
    return [(seg.start, seg.text.strip()) for seg in segments]


def _write_md(segments: list[tuple[float, str]], title: str, out_path: Path) -> None:
    """
    Write a timestamped markdown file from a list of (start_seconds, text) segments.

    Format:
        # <title>

        [00:00] First segment text
        [01:23] Second segment text
        ...

    The heading matches the title passed in by run() — usually the filename
    stem or the YouTube video title. /kos-ingest uses this heading when
    creating the wiki source page.
    """
    lines = [f"# {title}\n"]
    for start, text in segments:
        lines.append(f"{_fmt_time(start)} {text}")
    out_path.write_text("\n".join(lines) + "\n")


def run(
    source_type: str,
    source: str | Path,
    transcript_dir: Path,
    title: str,
    model_size: str = "base",
) -> Path:
    """
    Transcribe a source and write the output .md file. Returns the output path.

    This is the single entry point called by screens/transcribe.py.

    Arguments:
        source_type:    "meetings" | "youtube" | "podcasts"
        source:         local file Path for meetings; URL string for youtube/podcasts
        transcript_dir: destination directory (vault_root/raw/transcripts/<source_type>/)
        title:          used as the .md heading and filename stem
        model_size:     faster-whisper model size (default "base")

    Output filename: YYYY-MM-DD-<title-with-hyphens>.md
    Spaces in title are replaced with hyphens to keep filenames shell-friendly.

    For youtube/podcasts: audio is downloaded to a TemporaryDirectory that is
    automatically cleaned up after transcription, regardless of success or failure.
    The local machine retains only the .md transcript — no audio is kept.
    """
    transcript_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date.today().isoformat()}-{title.replace(' ', '-')}.md"
    out_path = transcript_dir / filename

    if source_type == "meetings":
        # Local MP4 — pass directly to faster-whisper, no download step needed.
        audio_path = Path(source)
        segments = _transcribe_audio(audio_path, model_size)
        _write_md(segments, title, out_path)
    else:
        # YouTube or Podcast — download audio to a temp dir, transcribe, then
        # let the TemporaryDirectory context manager delete the audio on exit.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            audio_path, _ = _download_audio(str(source), tmp_dir)
            segments = _transcribe_audio(audio_path, model_size)
            _write_md(segments, title, out_path)

    return out_path
