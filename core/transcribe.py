"""
core/transcribe.py

Local transcription engine wrapping faster-whisper and yt-dlp.

Source routing logic:
    - meetings:          always a local file → faster-whisper directly
    - youtube:           always a URL → yt-dlp download → faster-whisper
    - podcasts (URL):    http/https URL → yt-dlp download → faster-whisper
    - podcasts (local):  local file path → faster-whisper directly
                         supports MP3, WAV, M4A, and any format ffmpeg handles

Title resolution (run() title parameter):
    - Supplied:   used as-is for the .md heading and filename stem
    - None/blank: auto-derived — filename stem for local files,
                  yt-dlp's returned video/episode title for URLs

All transcription runs locally on CPU (int8 quantisation). No audio or
transcript data leaves the machine.

Output format:
    raw/transcripts/<source_type>/<title>-YYYY-MM-DD.md

    # <title>

    [MM:SS] segment text
    [MM:SS] segment text
    ...
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from datetime import date
from pathlib import Path

from faster_whisper import WhisperModel

SOURCE_TYPES = ["meetings", "youtube", "podcasts"]


def _is_url(source: str | Path) -> bool:
    """Return True when source looks like an http/https/ftp URL."""
    return str(source).startswith(("http://", "https://", "ftp://"))


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"[{m:02d}:{s:02d}]"


def _download_audio(
    url: str,
    tmp_dir: Path,
    on_dl_pct: Callable[[float], None] | None = None,
    source_type: str = "",
) -> tuple[Path, str]:
    """Download audio from a URL via yt-dlp; return (wav_path, title).

    Audio extracted to WAV so faster-whisper can read it without conversion.
    Raises RuntimeError if yt-dlp is not installed.
    """
    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError("yt-dlp is required for YouTube and Podcast URL transcription")

    def _progress_hook(d: dict) -> None:
        if on_dl_pct is None:
            return
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                on_dl_pct(min(downloaded / total, 1.0))
        elif d["status"] == "finished":
            on_dl_pct(1.0)

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(tmp_dir / "%(title)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_progress_hook],
    }
    if source_type == "youtube":
        # Strip community-tagged sponsor segments before transcription so they
        # never appear in the raw transcript — no extra dependency, yt-dlp calls
        # sponsor.ajay.app automatically when this key is set.
        opts["sponsorblock_remove"] = ["sponsor", "selfpromo", "interaction"]
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "audio")

    matches = list(tmp_dir.glob("*.wav"))
    if not matches:
        raise RuntimeError(f"yt-dlp produced no audio file for: {url}")
    return matches[0], title


def _transcribe_audio(
    audio_path: Path,
    model_size: str = "base",
    on_pct: Callable[[float], None] | None = None,
) -> list[tuple[float, str]]:
    """Run faster-whisper on any ffmpeg-readable audio file; return (start, text) pairs."""
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments_gen, info = model.transcribe(str(audio_path))
    total = info.duration or 0
    result = []
    for seg in segments_gen:
        result.append((seg.start, seg.text.strip()))
        if on_pct and total > 0:
            on_pct(min(seg.end / total, 1.0))
    return result


def _write_md(segments: list[tuple[float, str]], title: str, out_path: Path) -> None:
    lines = [f"# {title}\n"]
    for start, text in segments:
        lines.append(f"{_fmt_time(start)} {text}")
    out_path.write_text("\n".join(lines) + "\n")


def run(
    source_type: str,
    source: str | Path,
    transcript_dir: Path,
    title: str | None = None,
    model_size: str = "base",
    on_progress: Callable[[str], None] | None = None,
    on_pct: Callable[[float], None] | None = None,
    on_dl_pct: Callable[[float], None] | None = None,
    on_transcribing: Callable[[], None] | None = None,
) -> Path:
    """Transcribe a source and write the output .md. Returns the output path.

    Arguments:
        source_type:  "meetings" | "youtube" | "podcasts"
        source:       local file path or URL string
        transcript_dir: destination (vault_root/raw/transcripts/<source_type>/)
        title:        .md heading and filename stem; None = auto-derive
        model_size:   faster-whisper model size (default "base")
        on_progress:  optional callback(msg) called at each stage for live UI updates

    Routing:
        Local path (meetings always; podcasts when source is not a URL):
            faster-whisper reads the file directly — any format ffmpeg handles.
        URL (youtube always; podcasts when source starts with http/https/ftp):
            yt-dlp downloads to a TemporaryDirectory → faster-whisper → tmp cleaned up.
    """
    def _emit(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    transcript_dir.mkdir(parents=True, exist_ok=True)

    use_url = source_type == "youtube" or (source_type == "podcasts" and _is_url(source))

    if use_url:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _emit("Downloading audio via yt-dlp…")
            audio_path, yt_title = _download_audio(str(source), tmp_dir, on_dl_pct, source_type)
            _title = title or yt_title
            _emit(f'Audio ready — "{_title}"')
            _emit("Transcribing… this may take several minutes on CPU")
            if on_transcribing:
                on_transcribing()
            segments = _transcribe_audio(audio_path, model_size, on_pct)
    else:
        audio_path = Path(source).expanduser()
        _title = title or audio_path.stem
        _emit(f"Transcribing {audio_path.name}…")
        if on_transcribing:
            on_transcribing()
        segments = _transcribe_audio(audio_path, model_size, on_pct)

    filename = f"{_title.replace(' ', '-')}-{date.today().isoformat()}.md"
    out_path = transcript_dir / filename
    _write_md(segments, _title, out_path)
    _emit(f"Done — {out_path.name}")
    return out_path
