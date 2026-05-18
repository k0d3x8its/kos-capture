"""
core/vault.py

Path helpers for the user's KOS vault.

KOS Capture only interacts with the raw/ subtree of the vault — it never
reads or writes anything under wiki/. The boundary is strict: this module
resolves paths inside raw/, detects existing volume directories, and creates
new ones on demand. Nothing more.

Directory layout this module works with:

    <vault_root>/
    └── raw/
        ├── Field-Logs/
        │   ├── FL-vol-001/
        │   └── FL-vol-002/
        ├── Field-Research/
        │   └── FR-vol-001/
        ├── Field-Studies/
        │   └── FS-vol-001/
        └── transcripts/
            ├── meetings/
            ├── youtube/
            └── podcasts/
"""

from __future__ import annotations

from pathlib import Path

# The three scan collections, hardcoded per KOS spec.
# Each maps to a subdirectory under raw/ and uses a distinct volume prefix
# (FL-, FR-, FS-) enforced by convention, not by this module.
COLLECTIONS = ["Field-Logs", "Field-Research", "Field-Studies"]


def raw_root(vault_root: Path) -> Path:
    """Return the raw/ directory inside the vault. All paths derive from here."""
    return vault_root / "raw"


def volumes(vault_root: Path, collection: str) -> list[str]:
    """
    Return a sorted list of volume directory names for the given collection.

    Example: volumes(vault, "Field-Logs") → ["FL-vol-001", "FL-vol-002"]

    Returns an empty list if the collection directory doesn't exist yet
    (e.g. a brand-new vault). The wizard uses this to populate the volume
    picker and decide whether to show the '+ New volume' option.

    Only directories are included — any stray files in the collection folder
    are silently skipped.
    """
    collection_path = raw_root(vault_root) / collection
    if not collection_path.exists():
        return []
    return sorted(d.name for d in collection_path.iterdir() if d.is_dir())


def create_volume(vault_root: Path, collection: str, volume: str) -> Path:
    """
    Create a new volume directory and return its path.

    Called by the naming wizard when the user chooses '+ New volume' and
    confirms. mkdir(parents=True) ensures the collection directory is also
    created if it doesn't exist yet (possible on a fresh vault).
    exist_ok=True is a safety net — calling this twice for the same volume
    is harmless.
    """
    path = raw_root(vault_root) / collection / volume
    path.mkdir(parents=True, exist_ok=True)
    return path


def volume_path(vault_root: Path, collection: str, volume: str) -> Path:
    """
    Resolve the full path to an existing volume directory.

    Used by the naming wizard as the move destination. Does not create the
    directory — use create_volume() for that.
    """
    return raw_root(vault_root) / collection / volume


def transcript_path(vault_root: Path, source_type: str) -> Path:
    """
    Return the transcripts subdirectory for a given source type.

    source_type is one of: "meetings", "youtube", "podcasts"

    The directory is not created here — transcribe.run() calls
    mkdir(parents=True) when it writes the output file, so the directory
    is created on first use automatically.
    """
    return raw_root(vault_root) / "transcripts" / source_type
