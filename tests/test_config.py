"""
tests/test_config.py

Unit tests for core/config.py.

All filesystem tests use pytest's tmp_path fixture. CONFIG_PATH is patched
to point inside tmp_path so tests never touch the real config file.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

import core.config as config


# --- exists() ---

def test_exists_false(tmp_path):
    with patch.object(config, "CONFIG_PATH", tmp_path / "nonexistent.toml"):
        assert config.exists() is False


def test_exists_true(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[paths]\nproton_drive = "/a"\nvault_root = "/b"\nremote_path = "Photos/X"\n'
    )
    with patch.object(config, "CONFIG_PATH", cfg):
        assert config.exists() is True


# --- validate() ---

def test_validate_all_missing():
    errors = config.validate("/nonexistent/proton", "/nonexistent/vault", "")
    assert len(errors) == 3


def test_validate_paths_missing_remote_ok(tmp_path):
    errors = config.validate("/nonexistent/proton", "/nonexistent/vault", "Photos/X")
    assert len(errors) == 2


def test_validate_one_path_missing(tmp_path):
    errors = config.validate(str(tmp_path), "/nonexistent/vault", "Photos/X")
    assert len(errors) == 1


def test_validate_remote_empty(tmp_path):
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()
    errors = config.validate(str(proton), str(vault), "")
    assert len(errors) == 1
    assert "remote" in errors[0].lower()


def test_validate_all_valid(tmp_path):
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()
    assert config.validate(str(proton), str(vault), "Photos/Field-Notes") == []


# --- write() ---

def test_write_creates_file(tmp_path):
    cfg_path = tmp_path / "kos-capture" / "config.toml"
    with patch.object(config, "CONFIG_PATH", cfg_path):
        config.write(str(tmp_path / "proton"), str(tmp_path / "vault"), "Photos/X")
    assert cfg_path.exists()


def test_write_content(tmp_path):
    cfg_path = tmp_path / "config.toml"
    with patch.object(config, "CONFIG_PATH", cfg_path):
        config.write("/my/proton", "/my/vault", "Photos/Field-Notes")
    content = cfg_path.read_text()
    assert 'proton_drive = "/my/proton"' in content
    assert 'vault_root   = "/my/vault"' in content
    assert 'remote_path  = "Photos/Field-Notes"' in content


# --- tilde expansion ---

def test_validate_tilde_path_resolves(tmp_path, monkeypatch):
    """validate() expands ~ so home-relative paths that exist pass validation."""
    monkeypatch.setenv("HOME", str(tmp_path))
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()
    errors = config.validate("~/proton", "~/vault", "Photos/X")
    assert errors == []


def test_write_expands_tilde(tmp_path, monkeypatch):
    """write() stores absolute paths — ~ is never written to the config file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()
    cfg_path = tmp_path / "config.toml"
    with patch.object(config, "CONFIG_PATH", cfg_path):
        config.write("~/proton", "~/vault", "Photos/X")
    content = cfg_path.read_text()
    assert "~" not in content
    assert str(proton) in content
    assert str(vault) in content


# --- load() error handling ---

def test_load_bad_toml_raises_valueerror(tmp_path):
    """load() raises ValueError with a readable message when TOML is malformed."""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("this is not valid toml ][")
    with patch.object(config, "CONFIG_PATH", cfg_path):
        with pytest.raises(ValueError, match="not valid TOML"):
            config.load()


def test_load_missing_paths_section_raises_valueerror(tmp_path):
    """load() raises ValueError when the [paths] section is absent."""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("[other]\nkey = 'value'\n")
    with patch.object(config, "CONFIG_PATH", cfg_path):
        with pytest.raises(ValueError, match="missing required field"):
            config.load()


def test_load_missing_field_raises_valueerror(tmp_path):
    """load() raises ValueError when a required key is absent from [paths]."""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[paths]\nproton_drive = "/a"\nvault_root = "/b"\n')
    with patch.object(config, "CONFIG_PATH", cfg_path):
        with pytest.raises(ValueError, match="missing required field"):
            config.load()


# --- load() ---

def test_write_and_load_roundtrip(tmp_path):
    proton = tmp_path / "proton"; proton.mkdir()
    vault  = tmp_path / "vault";  vault.mkdir()
    cfg_path = tmp_path / "config.toml"
    with patch.object(config, "CONFIG_PATH", cfg_path):
        config.write(str(proton), str(vault), "Photos/Field-Notes")
        cfg = config.load()
    assert cfg.proton_drive == proton
    assert cfg.vault_root == vault
    assert cfg.remote_path == "Photos/Field-Notes"
