"""
core/config.py

Handles reading and writing the user config file located at:
    ~/.config/kos-capture/config.toml

The config stores two paths:
    - proton_drive: local directory where rclone syncs Field Notes PDFs from Proton Drive
    - vault_root:   root directory of the user's KOS vault (contains raw/, wiki/, etc.)

These two paths are the only user-supplied values. Everything else in the app
is derived from them at runtime — no hardcoded defaults anywhere.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# tomllib was added to the Python standard library in 3.11.
# For Python 3.10 compatibility we fall back to the third-party tomli package,
# which has an identical API. Both are aliased to `tomllib` so the rest of the
# module doesn't need to branch.
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# XDG-style config location. The parent directory is created on first write if
# it doesn't exist yet (see write() below).
CONFIG_PATH = Path.home() / ".config" / "kos-capture" / "config.toml"


@dataclass
class Config:
    """
    Typed container for the two user-configured paths.

    Both fields are Path objects so callers can use path arithmetic directly
    (e.g. config.vault_root / "raw") without casting strings everywhere.
    """
    proton_drive: Path  # local Proton Drive sync folder
    vault_root: Path    # root of the KOS vault


def exists() -> bool:
    """
    Return True if a config file is present on disk.

    Called at app startup (main.py) to decide whether to show the setup screen
    or go straight to the home screen.
    """
    return CONFIG_PATH.exists()


def load() -> Config:
    """
    Parse the config file and return a Config dataclass.

    Raises FileNotFoundError if the config doesn't exist — callers should
    check exists() first, or let the exception surface as a bug (missing
    guard in main.py).

    TOML loaders require the file to be opened in binary mode ('rb') because
    the spec mandates UTF-8 encoding detection from the raw bytes.
    """
    with CONFIG_PATH.open("rb") as f:
        data = tomllib.load(f)
    paths = data["paths"]
    return Config(
        proton_drive=Path(paths["proton_drive"]),
        vault_root=Path(paths["vault_root"]),
    )


def validate(proton_drive: str, vault_root: str) -> list[str]:
    """
    Check that both paths exist on disk before writing the config.

    Returns a list of human-readable error strings — empty means valid.
    Returning all errors at once (rather than raising on the first) lets the
    setup screen highlight every problem in a single pass instead of making
    the user fix and resubmit one error at a time.
    """
    errors = []
    if not Path(proton_drive).exists():
        errors.append(f"Proton Drive path not found: {proton_drive}")
    if not Path(vault_root).exists():
        errors.append(f"Vault root not found: {vault_root}")
    return errors


def write(proton_drive: str, vault_root: str) -> None:
    """
    Persist both paths to ~/.config/kos-capture/config.toml.

    Creates the parent directory if it doesn't exist (first-run case).

    The TOML is written as a raw string rather than using a serialisation
    library because tomllib/tomli are read-only by design, and adding tomli-w
    as a dependency for two lines of config is not worth it. The structure
    is fixed and simple enough that manual formatting is safe here.
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        f'[paths]\nproton_drive = "{proton_drive}"\nvault_root   = "{vault_root}"\n'
    )
