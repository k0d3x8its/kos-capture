"""
main.py

Entry point for KOS Capture.

Checks for an existing config file before launching the app. If no config
is found (first run), the app opens on the Setup screen so the user can
set their Proton Drive path and vault root before anything else loads.
If a config exists, the app opens directly on the Home screen.

Run:
    python main.py
"""

from app import KosCaptureApp
import core.config as config


def main() -> None:
    app = KosCaptureApp()

    if config.exists():
        # Config present — go straight to Home
        app.push_screen("home")
    else:
        # First run — route to Setup so the user can configure paths
        app.push_screen("setup")

    app.run()


if __name__ == "__main__":
    main()
