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


def test_on_mount_initialises_session_results():
    """on_mount() creates session_results as an empty list."""
    app = KosCaptureApp()
    with patch("app.config.exists", return_value=False), \
         patch.object(app, "push_screen"), \
         patch.object(app, "register_theme", wraps=app.register_theme):
        app.on_mount()
    assert hasattr(app, "session_results")
    assert app.session_results == []


# ── clipboard property ───────────────────────────────────────────────────────

import subprocess as _subprocess


def test_clipboard_returns_wl_paste_output():
    """clipboard property returns wl-paste output when available."""
    app = KosCaptureApp()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "https://example.com"
    with patch("subprocess.run", return_value=mock_result):
        assert app.clipboard == "https://example.com"


def test_clipboard_falls_back_to_xclip():
    """clipboard property skips wl-paste (FileNotFoundError) and uses xclip."""
    app = KosCaptureApp()

    xclip_result = MagicMock()
    xclip_result.returncode = 0
    xclip_result.stdout = "from xclip"

    def _side_effect(cmd, **kwargs):
        if cmd[0] == "wl-paste":
            raise FileNotFoundError
        return xclip_result

    with patch("subprocess.run", side_effect=_side_effect):
        assert app.clipboard == "from xclip"


def test_clipboard_falls_back_to_xsel():
    """clipboard property falls through wl-paste and xclip to xsel."""
    app = KosCaptureApp()

    xsel_result = MagicMock()
    xsel_result.returncode = 0
    xsel_result.stdout = "from xsel"

    def _side_effect(cmd, **kwargs):
        if cmd[0] in ("wl-paste", "xclip"):
            raise FileNotFoundError
        return xsel_result

    with patch("subprocess.run", side_effect=_side_effect):
        assert app.clipboard == "from xsel"


def test_clipboard_returns_empty_when_all_fail():
    """clipboard property returns empty string when all backends are missing."""
    app = KosCaptureApp()
    app._clipboard = ""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert app.clipboard == ""


def test_clipboard_skips_nonzero_returncode():
    """clipboard property skips a backend that returns a non-zero exit code."""
    app = KosCaptureApp()
    app._clipboard = ""

    fail_result = MagicMock()
    fail_result.returncode = 1
    fail_result.stdout = ""

    with patch("subprocess.run", return_value=fail_result):
        assert app.clipboard == ""
