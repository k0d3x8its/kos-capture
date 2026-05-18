"""
app.py

Textual App class for KOS Capture.

Registers all screens and defines global keybindings. This is the central
wiring point — it knows about every screen but contains no business logic.
All logic lives in core/ (data) and screens/ (UI).

Screen navigation model:
    - Home, Sync, Inbox, Transcribe are top-level screens — navigable
      directly via keybindings at any time.
    - Setup is pushed on first launch (from main.py) or from Home when
      the user wants to update config.
    - Wizard and Ready are flow screens — pushed by Inbox and Transcribe
      respectively, then popped when the flow completes.
"""

from textual.app import App
from textual.binding import Binding

from screens.home import HomeScreen
from screens.setup import SetupScreen
from screens.sync import SyncScreen
from screens.inbox import InboxScreen
from screens.wizard import WizardScreen
from screens.transcribe import TranscribeScreen
from screens.ready import ReadyScreen


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
