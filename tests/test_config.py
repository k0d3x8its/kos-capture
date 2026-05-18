"""
tests/test_config.py

Unit tests for core/config.py.

All tests that touch the filesystem use pytest's tmp_path fixture, which
provides a unique temporary directory per test. CONFIG_PATH is patched to
point inside tmp_path so tests never read from or write to the real
~/.config/kos-capture/config.toml.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

import core.config as config


# --- exists() ---

def test_exists_false(tmp_path):
    """exists() returns False when no config file is present."""
    with patch.object(config, "CONFIG_PATH", tmp_path / "nonexistent.toml"):
        assert config.exists() is False


def test_exists_true(tmp_path):
    """exists() returns True when a config file is present, regardless of content."""
    cfg = tmp_path / "config.toml"
    cfg.write_text('[paths]\nproton_drive = "/a"\nvault_root = "/b"\n')
    with patch.object(config, "CONFIG_PATH", cfg):
        assert config.exists() is True


# --- validate() ---

def test_validate_both_missing():
    """validate() returns two errors when both paths don't exist."""
    errors = config.validate("/nonexistent/proton", "/nonexistent/vault")
    assert len(errors) == 2


def test_validate_one_missing(tmp_path):
    """validate() returns one error when only one path is missing."""
    errors = config.validate(str(tmp_path), "/nonexistent/vault")
    assert len(errors) == 1


def test_validate_both_exist(tmp_path):
    """validate() returns empty list when both paths exist on disk."""
    proton = tmp_path / "proton"
    vault = tmp_path / "vault"
    proton.mkdir()
    vault.mkdir()
    assert config.validate(str(proton), str(vault)) == []


# --- write() ---

def test_write_creates_file(tmp_path):
    """write() creates the config file and any missing parent directories."""
    cfg_path = tmp_path / "kos-capture" / "config.toml"
    with patch.object(config, "CONFIG_PATH", cfg_path):
        config.write(str(tmp_path / "proton"), str(tmp_path / "vault"))
    assert cfg_path.exists()


def test_write_content(tmp_path):
    """write() stores both paths correctly in TOML format."""
    cfg_path = tmp_path / "config.toml"
    with patch.object(config, "CONFIG_PATH", cfg_path):
        config.write("/my/proton", "/my/vault")
    content = cfg_path.read_text()
    assert 'proton_drive = "/my/proton"' in content
    assert 'vault_root   = "/my/vault"' in content


# --- load() ---

def test_write_and_load_roundtrip(tmp_path):
    """write() followed by load() returns a Config with matching Path values."""
    proton = tmp_path / "proton"
    vault = tmp_path / "vault"
    proton.mkdir()
    vault.mkdir()
    cfg_path = tmp_path / "config.toml"
    with patch.object(config, "CONFIG_PATH", cfg_path):
        config.write(str(proton), str(vault))
        cfg = config.load()
    # load() returns Path objects, not strings
    assert cfg.proton_drive == proton
    assert cfg.vault_root == vault
