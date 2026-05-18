"""
tests/test_main.py

Unit tests for main.py.

KosCaptureApp and config.exists() are mocked so no Textual event loop
runs and no filesystem is touched. Tests verify only the routing logic —
that main() pushes the correct screen based on whether a config exists.
"""

from unittest.mock import MagicMock, patch

import main


def test_routes_to_setup_on_first_run():
    """main() pushes 'setup' when no config file is present."""
    mock_app = MagicMock()
    with patch("main.KosCaptureApp", return_value=mock_app), \
         patch("main.config.exists", return_value=False):
        main.main()
    mock_app.push_screen.assert_called_once_with("setup")


def test_routes_to_home_when_config_exists():
    """main() pushes 'home' when a config file is already present."""
    mock_app = MagicMock()
    with patch("main.KosCaptureApp", return_value=mock_app), \
         patch("main.config.exists", return_value=True):
        main.main()
    mock_app.push_screen.assert_called_once_with("home")


def test_app_run_called():
    """main() always calls app.run() regardless of config state."""
    mock_app = MagicMock()
    with patch("main.KosCaptureApp", return_value=mock_app), \
         patch("main.config.exists", return_value=False):
        main.main()
    mock_app.run.assert_called_once()
