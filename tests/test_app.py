"""
tests/test_app.py

Unit tests for app.py.

Tests check class-level attributes only — no Textual event loop is started.
This keeps the suite fast and avoids the async overhead of App.run_test()
for what are essentially configuration checks.
"""

from app import KosCaptureApp
from screens.home import HomeScreen
from screens.setup import SetupScreen
from screens.sync import SyncScreen
from screens.inbox import InboxScreen
from screens.wizard import WizardScreen
from screens.transcribe import TranscribeScreen
from screens.ready import ReadyScreen


def test_app_title():
    """App title matches the expected product name."""
    assert KosCaptureApp.TITLE == "KOS Capture"


def test_all_screens_registered():
    """All seven screens are present in the SCREENS registry."""
    expected = {"home", "setup", "sync", "inbox", "wizard", "transcribe", "ready"}
    assert expected == set(KosCaptureApp.SCREENS.keys())


def test_screen_classes_are_correct():
    """Each registry key maps to the correct Screen subclass."""
    assert KosCaptureApp.SCREENS["home"] is HomeScreen
    assert KosCaptureApp.SCREENS["setup"] is SetupScreen
    assert KosCaptureApp.SCREENS["sync"] is SyncScreen
    assert KosCaptureApp.SCREENS["inbox"] is InboxScreen
    assert KosCaptureApp.SCREENS["wizard"] is WizardScreen
    assert KosCaptureApp.SCREENS["transcribe"] is TranscribeScreen
    assert KosCaptureApp.SCREENS["ready"] is ReadyScreen


def test_quit_binding_exists():
    """ctrl+q quit binding is registered with priority."""
    bindings = {b.key: b for b in KosCaptureApp.BINDINGS}
    assert "ctrl+q" in bindings
    assert bindings["ctrl+q"].priority is True


def test_nav_bindings_exist():
    """Top-level navigation bindings h, s, i, t are all registered."""
    keys = {b.key for b in KosCaptureApp.BINDINGS}
    for key in ("h", "s", "i", "t"):
        assert key in keys, f"Missing nav binding: {key}"
