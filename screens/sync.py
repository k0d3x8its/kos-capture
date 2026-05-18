# screens/sync.py — rclone last sync time, systemd timer status, manual trigger button

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class SyncScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static("KOS Capture — Sync [stub]")
