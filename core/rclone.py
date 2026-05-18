"""
core/rclone.py

Wrapper around the rclone CLI and the proton-sync.timer systemd unit.

KOS Capture does not configure rclone — that's a one-time manual step the
user completes before first run (see README Prerequisites). This module only
queries status and triggers syncs against an already-configured remote.

Assumptions:
    - The systemd user timer unit is named `proton-sync.timer`
    - The rclone remote is named `protondrive:` (default for trigger_sync)
    - rclone is on the system PATH
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class RcloneStatus:
    """
    Snapshot of rclone + systemd state, collected once per screen refresh.

    Bundling all three values into a dataclass means the Home and Sync screens
    can call status() once and read from the result — no repeated subprocess
    calls per field.
    """
    installed: bool        # True if `rclone` binary is on PATH
    timer_active: bool     # True if proton-sync.timer is in the 'active' state
    last_sync: datetime | None  # When the timer last fired; None if never or unknown


def is_installed() -> bool:
    """
    Check whether the rclone binary is available on PATH.

    Runs `rclone version` with check=True so any non-zero exit is treated as
    a failure. Catches FileNotFoundError (binary missing) and
    CalledProcessError (binary exists but broken) separately so both cases
    return False cleanly.
    """
    try:
        subprocess.run(["rclone", "version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def timer_active() -> bool:
    """
    Return True if the proton-sync.timer systemd user unit is active.

    `systemctl --user is-active` exits 0 and prints 'active' when the unit
    is running, or prints a non-active state string (inactive, failed, etc.)
    when it isn't. We don't use the exit code here — we read the text output
    directly because it's more explicit.
    """
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "proton-sync.timer"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == "active"


def last_sync_time() -> datetime | None:
    """
    Return the datetime of the most recent timer trigger, or None.

    `systemctl show --property=LastTriggerUSec` returns a line like:
        LastTriggerUSec=Mon 2026-05-18 10:30:00 UTC

    A value of '0' or an empty string means the timer has never fired
    (e.g. just installed, or unit reset). In that case we return None so
    callers can display 'Never' rather than an epoch timestamp.

    The datetime format from systemd is: %a %Y-%m-%d %H:%M:%S %Z
    """
    result = subprocess.run(
        [
            "systemctl", "--user", "show", "proton-sync.timer",
            "--property=LastTriggerUSec",
        ],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("LastTriggerUSec="):
            value = line.split("=", 1)[1].strip()
            if value and value != "0":
                try:
                    return datetime.strptime(value, "%a %Y-%m-%d %H:%M:%S %Z")
                except ValueError:
                    return None
    return None


def status() -> RcloneStatus:
    """
    Collect all three status values and return them as a single dataclass.

    Called by the Home screen on mount and by the Sync screen on refresh.
    Each sub-call runs a separate subprocess — fast enough for a status
    snapshot, not suitable for tight polling loops.
    """
    return RcloneStatus(
        installed=is_installed(),
        timer_active=timer_active(),
        last_sync=last_sync_time(),
    )


def trigger_sync(proton_drive: Path, remote: str = "protondrive:") -> subprocess.Popen:
    """
    Start a manual rclone sync and return the running process.

    Returns a Popen object rather than waiting for completion so the Sync
    screen can stream stdout line-by-line and display live progress without
    blocking the Textual event loop. The caller is responsible for reading
    proc.stdout and calling proc.wait() when done.

    stderr is merged into stdout (STDOUT) so progress messages and errors
    appear in the same stream.

    The `remote` argument defaults to 'protondrive:' — the standard rclone
    remote name for Proton Drive. Override if the user configured a different
    remote name (future config option).
    """
    return subprocess.Popen(
        ["rclone", "sync", remote, str(proton_drive), "--progress"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
