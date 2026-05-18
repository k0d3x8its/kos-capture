"""
tests/test_vault.py

Unit tests for core/vault.py.

All tests use tmp_path as a stand-in for vault_root so nothing is written
to the real KOS vault during testing. The raw/ subdirectory structure is
created manually inside tmp_path to simulate different vault states.
"""

import pytest
from pathlib import Path

import core.vault as vault


# --- volumes() ---

def test_volumes_empty(tmp_path):
    """volumes() returns empty list when the collection directory doesn't exist."""
    assert vault.volumes(tmp_path, "Field-Logs") == []


def test_volumes_missing_collection(tmp_path):
    """volumes() handles a missing collection gracefully — no exception raised."""
    assert vault.volumes(tmp_path, "Field-Research") == []


def test_volumes_detected(tmp_path):
    """volumes() returns sorted directory names for an existing collection."""
    coll = tmp_path / "raw" / "Field-Logs"
    (coll / "FL-vol-002").mkdir(parents=True)
    (coll / "FL-vol-001").mkdir(parents=True)
    # Result must be sorted ascending — wizard displays them in order
    assert vault.volumes(tmp_path, "Field-Logs") == ["FL-vol-001", "FL-vol-002"]


def test_volumes_ignores_files(tmp_path):
    """volumes() skips files in the collection directory — only dirs count as volumes."""
    coll = tmp_path / "raw" / "Field-Logs"
    coll.mkdir(parents=True)
    (coll / "FL-vol-001").mkdir()
    (coll / "stray.md").write_text("")  # stray file — should be ignored
    assert vault.volumes(tmp_path, "Field-Logs") == ["FL-vol-001"]


# --- create_volume() ---

def test_create_volume(tmp_path):
    """create_volume() creates the directory on disk."""
    path = vault.create_volume(tmp_path, "Field-Logs", "FL-vol-001")
    assert path.exists()
    assert path.is_dir()


def test_create_volume_returns_correct_path(tmp_path):
    """create_volume() returns the full path to the new volume directory."""
    path = vault.create_volume(tmp_path, "Field-Research", "FR-vol-001")
    assert path == tmp_path / "raw" / "Field-Research" / "FR-vol-001"


# --- volume_path() ---

def test_volume_path(tmp_path):
    """volume_path() resolves the correct path without creating anything."""
    path = vault.volume_path(tmp_path, "Field-Studies", "FS-vol-003")
    assert path == tmp_path / "raw" / "Field-Studies" / "FS-vol-003"


# --- transcript_path() ---

def test_transcript_path_meetings(tmp_path):
    """transcript_path() resolves raw/transcripts/meetings/ correctly."""
    path = vault.transcript_path(tmp_path, "meetings")
    assert path == tmp_path / "raw" / "transcripts" / "meetings"


def test_transcript_path_youtube(tmp_path):
    """transcript_path() resolves raw/transcripts/youtube/ correctly."""
    path = vault.transcript_path(tmp_path, "youtube")
    assert path == tmp_path / "raw" / "transcripts" / "youtube"


def test_transcript_path_podcasts(tmp_path):
    """transcript_path() resolves raw/transcripts/podcasts/ correctly."""
    path = vault.transcript_path(tmp_path, "podcasts")
    assert path == tmp_path / "raw" / "transcripts" / "podcasts"
