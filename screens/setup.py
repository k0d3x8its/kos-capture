# screens/setup.py — first-run config UI, prompts for Proton Drive path + vault root, writes config.toml

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class SetupScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static("KOS Capture — Setup [stub]")
