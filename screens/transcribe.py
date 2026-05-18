# screens/transcribe.py — source type selector: Proton Meet / YouTube / Podcast

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class TranscribeScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static("KOS Capture — Transcribe [stub]")
