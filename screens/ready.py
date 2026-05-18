# screens/ready.py — display exact file paths of all files moved or transcribed in the session

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class ReadyScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static("KOS Capture — Ready [stub]")
