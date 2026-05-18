# screens/inbox.py — list PDFs detected in Proton Drive sync folder awaiting processing

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class InboxScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static("KOS Capture — Inbox [stub]")
