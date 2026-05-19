"""
screens/modal.py

Reusable error modal for surfacing configuration and system errors.

Pushed on top of any screen when something requires user attention.
Escape or Dismiss closes the modal and returns to the calling screen.
"Open Setup" routes the user to the setup screen to fix their config.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ErrorModal(ModalScreen):

    BINDINGS = [Binding("escape", "dismiss_modal", "Dismiss")]

    DEFAULT_CSS = """
    ErrorModal {
        align: center middle;
    }

    #modal-panel {
        width: 60;
        height: auto;
        border: round $error;
        padding: 1 2;
        background: $surface;
    }

    #modal-title {
        text-align: center;
        text-style: bold;
        color: $error;
        height: 1;
        margin-bottom: 1;
    }

    #modal-message {
        margin-bottom: 1;
    }

    #modal-setup {
        width: 100%;
        margin-bottom: 1;
    }

    #modal-dismiss {
        width: 100%;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-panel"):
            yield Static("Configuration Error", id="modal-title")
            yield Static(self._message, id="modal-message")
            yield Button("Open Setup", id="modal-setup", variant="error")
            yield Button("Dismiss", id="modal-dismiss")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "modal-setup":
            self.dismiss("setup")
        else:
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
