# screens/home.py — ASCII splash screen via pyfiglet + system status summary

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class HomeScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static("KOS Capture — Home [stub]")
