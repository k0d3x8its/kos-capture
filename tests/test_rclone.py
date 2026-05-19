"""
tests/test_rclone.py

Unit tests for core/rclone.py.

All subprocess calls are mocked — tests never invoke rclone or systemctl.
This keeps the suite fast and runnable on machines without rclone installed
(including CI runners).
"""

import subprocess
from unittest.mock import MagicMock, patch

import core.rclone as rclone


# --- is_installed() ---

def test_is_installed_true():
    """is_installed() returns True when `rclone version` exits cleanly."""
    with patch("subprocess.run", return_value=MagicMock(returncode=0)):
        assert rclone.is_installed() is True


def test_is_installed_missing_binary():
    """is_installed() returns False when the rclone binary is not on PATH."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert rclone.is_installed() is False


def test_is_installed_nonzero_exit():
    """is_installed() returns False when rclone exits with a non-zero code."""
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "rclone")):
        assert rclone.is_installed() is False


# --- timer_active() ---

def test_timer_active_true():
    """timer_active() returns True when systemctl reports 'active'."""
    result = MagicMock()
    result.stdout = "active\n"
    with patch("subprocess.run", return_value=result):
        assert rclone.timer_active() is True


def test_timer_active_false():
    """timer_active() returns False for any non-active systemd state."""
    result = MagicMock()
    result.stdout = "inactive\n"
    with patch("subprocess.run", return_value=result):
        assert rclone.timer_active() is False


# --- last_sync_time() ---

def test_last_sync_time_zero_returns_none():
    """last_sync_time() returns None when LastTriggerUSec is '0' (timer never fired)."""
    result = MagicMock()
    result.stdout = "LastTriggerUSec=0\n"
    with patch("subprocess.run", return_value=result):
        assert rclone.last_sync_time() is None


def test_last_sync_time_empty_returns_none():
    """last_sync_time() returns None when LastTriggerUSec value is empty."""
    result = MagicMock()
    result.stdout = "LastTriggerUSec=\n"
    with patch("subprocess.run", return_value=result):
        assert rclone.last_sync_time() is None


def test_last_sync_time_malformed_returns_none():
    """last_sync_time() returns None when the timestamp cannot be parsed (ValueError branch)."""
    result = MagicMock()
    result.stdout = "LastTriggerUSec=not a valid date\n"
    with patch("subprocess.run", return_value=result):
        assert rclone.last_sync_time() is None


def test_last_sync_time_parses_valid():
    """last_sync_time() parses a valid systemd timestamp into a datetime."""
    result = MagicMock()
    result.stdout = "LastTriggerUSec=Mon 2026-05-18 10:30:00 UTC\n"
    with patch("subprocess.run", return_value=result):
        dt = rclone.last_sync_time()
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 18
        assert dt.hour == 10
        assert dt.minute == 30


# --- status() ---

def test_status_returns_dataclass():
    """status() aggregates all three sub-calls into a single RcloneStatus."""
    with patch("core.rclone.is_installed", return_value=True), \
         patch("core.rclone.timer_active", return_value=False), \
         patch("core.rclone.last_sync_time", return_value=None):
        s = rclone.status()
        assert s.installed is True
        assert s.timer_active is False
        assert s.last_sync is None


# --- trigger_sync() ---

def test_trigger_sync_builds_correct_command(tmp_path):
    """trigger_sync() passes proton:{remote_path} as the rclone source."""
    mock_proc = MagicMock()
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        rclone.trigger_sync(tmp_path, "Photos/Field-Notes")
        args = mock_popen.call_args[0][0]
        assert args[0] == "rclone"
        assert args[1] == "copy"
        assert args[2] == "proton:Photos/Field-Notes"
        assert args[3] == str(tmp_path)


def test_trigger_sync_strips_leading_slash(tmp_path):
    """trigger_sync() strips a leading slash from remote_path."""
    mock_proc = MagicMock()
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        rclone.trigger_sync(tmp_path, "/Photos/Field-Notes")
        args = mock_popen.call_args[0][0]
        assert args[2] == "proton:Photos/Field-Notes"
