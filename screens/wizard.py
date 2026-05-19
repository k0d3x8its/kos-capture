# screens/wizard.py — per-file: apply suffix (-sticky/-under/-flip), select collection + volume, confirm move

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static


class WizardScreen(Screen):

    BINDINGS = [Binding("escape", "go_back", "Back")]

    def __init__(self, file_path: Path) -> None:
        super().__init__()
        self.file_path = file_path

    def compose(self) -> ComposeResult:
        yield Static(f"KOS Capture — Naming Wizard [stub]\n\nFile: {self.file_path.name}")

    def action_go_back(self) -> None:
        self.app.pop_screen()
