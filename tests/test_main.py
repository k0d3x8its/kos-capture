"""
tests/test_main.py

Unit tests for main.py.

main() now only instantiates and runs the app — routing logic moved to
KosCaptureApp.on_mount(). Tests verify the app is created and run() is called.
Routing is tested in test_app.py via on_mount.
"""

from unittest.mock import MagicMock, patch

import main


def test_app_is_instantiated_and_run():
    """main() creates a KosCaptureApp and calls run()."""
    mock_app = MagicMock()
    with patch("main.KosCaptureApp", return_value=mock_app):
        main.main()
    mock_app.run.assert_called_once()
