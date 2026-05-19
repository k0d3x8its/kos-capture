"""
app.py

Textual App class for KOS Capture.

Registers all screens and defines global keybindings. This is the central
wiring point — it knows about every screen but contains no business logic.
All logic lives in core/ (data) and screens/ (UI).

Screen navigation model:
    - Home, Sync, Inbox, Transcribe are top-level screens — navigable
      directly via keybindings at any time.
    - Setup is pushed on first launch (from on_mount) or from Home when
      the user wants to update config.
    - Wizard and Ready are flow screens — pushed by Inbox and Transcribe
      respectively, then popped when the flow completes.
"""

from pathlib import Path

import core.config as config
from textual.app import App
from textual.binding import Binding
from textual.theme import Theme

from screens.home import HomeScreen
from screens.inbox import InboxScreen
from screens.ready import ReadyScreen
from screens.setup import SetupScreen
from screens.sync import SyncScreen
from screens.transcribe import TranscribeScreen
from screens.wizard import WizardScreen

# Classic terminal green palette
TERMINAL_GREEN = Theme(
    name="terminal-green",
    dark=True,
    primary="#00ff41",       # matrix green — buttons, borders, highlights
    secondary="#00cc33",     # slightly dimmer green — secondary elements
    accent="#39ff14",        # neon green — focused/active states
    background="#000000",    # pure black
    surface="#0a150a",       # dark green-tinted surface for panels
    panel="#0d1a0d",         # slightly lighter panel background
    foreground="#00ff41",    # green text throughout
    success="#00ff41",       # success messages in green
    warning="#ffaa00",       # amber — distinct from green so warnings stand out
    error="#ff3333",         # red — distinct so errors are unmistakable
)


class KosCaptureApp(App):

    TITLE = "KOS Capture"
    SUB_TITLE = "field capture pipeline"

    # Named screen registry — screens are instantiated on first push, not at
    # startup, so importing them here doesn't trigger any heavy initialisation.
    SCREENS = {
        "home": HomeScreen,
        "setup": SetupScreen,
        "sync": SyncScreen,
        "inbox": InboxScreen,
        "wizard": WizardScreen,
        "transcribe": TranscribeScreen,
        "ready": ReadyScreen,
    }

    BINDINGS = [
        # priority=True ensures ctrl+q works even when a widget captures input
        Binding("ctrl+q", "quit", "Quit", priority=True),
        # Top-level screen navigation — not shown in footer on flow screens
        Binding("h", "switch_screen('home')", "Home"),
        Binding("s", "switch_screen('sync')", "Sync"),
        Binding("i", "switch_screen('inbox')", "Inbox"),
        Binding("t", "switch_screen('transcribe')", "Transcribe"),
    ]

    def on_mount(self) -> None:
        self.session_results: list[Path] = []
        """Apply theme and route to the correct initial screen.

        push_screen() requires the app to be running — calling it before
        app.run() is silently ignored and causes a blank screen. on_mount
        fires after startup, making it the correct place for initial routing.
        """
        self.register_theme(TERMINAL_GREEN)
        self.theme = "terminal-green"

        if config.exists():
            self.push_screen("home")
        else:
            self.push_screen("setup")
