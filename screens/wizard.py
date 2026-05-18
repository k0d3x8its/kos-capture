# screens/wizard.py — per-file: apply suffix (-sticky/-under/-flip), select collection + volume, confirm move

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class WizardScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static("KOS Capture — Naming Wizard [stub]")
