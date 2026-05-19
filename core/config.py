"""
core/config.py

Handles reading and writing the user config file located at:
    ~/.config/kos-capture/config.toml

The config stores three values:
    - proton_drive:  local directory where rclone syncs Field Notes PDFs
    - vault_root:    root directory of the user's KOS vault (contains raw/, wiki/, etc.)
    - remote_path:   subfolder path on the Proton Drive remote to sync from
                     (e.g. "Photos/Field-Notes") — combined with the remote name
                     at sync time: proton:Photos/Field-Notes

These are the only user-supplied values. Everything else in the app is
derived from them at runtime — no hardcoded defaults anywhere.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

CONFIG_PATH = Path.home() / ".config" / "kos-capture" / "config.toml"


@dataclass
class Config:
    proton_drive: Path  # local Proton Drive sync folder
    vault_root: Path    # root of the KOS vault
    remote_path: str    # subfolder on the remote, e.g. "Photos/Field-Notes"


def exists() -> bool:
    return CONFIG_PATH.exists()


def load() -> Config:
    with CONFIG_PATH.open("rb") as f:
        data = tomllib.load(f)
    paths = data["paths"]
    return Config(
        proton_drive=Path(paths["proton_drive"]),
        vault_root=Path(paths["vault_root"]),
        remote_path=paths["remote_path"],
    )


def validate(proton_drive: str, vault_root: str, remote_path: str) -> list[str]:
    """
    Validate all three config values before writing.

    Paths are expanded (~ → home dir) before checking existence.
    remote_path must be non-empty but is not checked against the remote.
    """
    errors = []
    if not Path(proton_drive).expanduser().exists():
        errors.append(f"Proton Drive path not found: {proton_drive}")
    if not Path(vault_root).expanduser().exists():
        errors.append(f"Vault root not found: {vault_root}")
    if not remote_path.strip():
        errors.append("Remote path is required (e.g. Photos/Field-Notes).")
    return errors


def write(proton_drive: str, vault_root: str, remote_path: str) -> None:
    """Persist all three config values to ~/.config/kos-capture/config.toml.

    Paths are expanded to absolute form before storing so ~ never appears
    in the saved file.
    """
    proton_abs = str(Path(proton_drive).expanduser().resolve())
    vault_abs  = str(Path(vault_root).expanduser().resolve())
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        f'[paths]\n'
        f'proton_drive = "{proton_abs}"\n'
        f'vault_root   = "{vault_abs}"\n'
        f'remote_path  = "{remote_path.strip()}"\n'
    )
