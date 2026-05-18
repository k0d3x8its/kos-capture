"""
tests/test_app.py

Unit tests for app.py.

Tests check class-level attributes only — no Textual event loop is started.
This keeps the suite fast and avoids the async overhead of App.run_test()
for what are essentially configuration checks.
"""

from unittest.mock import MagicMock, patch

from app import KosCaptureApp, TERMINAL_GREEN
from screens.home import HomeScreen
from screens.inbox import InboxScreen
from screens.ready import ReadyScreen
from screens.setup import SetupScreen
from screens.sync import SyncScreen
from screens.transcribe import TranscribeScreen
from screens.wizard import WizardScreen


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


def test_terminal_green_theme_name():
    """TERMINAL_GREEN theme has the correct name for registration."""
    assert TERMINAL_GREEN.name == "terminal-green"


def test_terminal_green_is_dark():
    """TERMINAL_GREEN theme is flagged as a dark theme."""
    assert TERMINAL_GREEN.dark is True


def test_on_mount_registers_theme_and_routes_to_setup():
    """on_mount() registers the theme, sets it, and pushes setup when no config."""
    app = KosCaptureApp()
    # wraps=... calls the real register_theme so the theme is actually registered
    # (required for self.theme = "terminal-green" to pass validation), while
    # still letting us assert it was called with the right argument.
    with patch("app.config.exists", return_value=False), \
         patch.object(app, "push_screen") as mock_push, \
         patch.object(app, "register_theme", wraps=app.register_theme) as mock_register:
        app.on_mount()
    mock_register.assert_called_once_with(TERMINAL_GREEN)
    assert app.theme == "terminal-green"
    mock_push.assert_called_once_with("setup")


def test_on_mount_registers_theme_and_routes_to_home():
    """on_mount() registers the theme, sets it, and pushes home when config exists."""
    app = KosCaptureApp()
    with patch("app.config.exists", return_value=True), \
         patch.object(app, "push_screen") as mock_push, \
         patch.object(app, "register_theme", wraps=app.register_theme) as mock_register:
        app.on_mount()
    mock_register.assert_called_once_with(TERMINAL_GREEN)
    assert app.theme == "terminal-green"
    mock_push.assert_called_once_with("home")
