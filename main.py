"""
main.py

Entry point for KOS Capture. Instantiates and runs the app.

Initial screen routing (setup vs home) is handled in KosCaptureApp.on_mount()
rather than here — push_screen() requires the Textual event loop to be
running and has no effect when called before app.run().

Run:
    python main.py
"""

from app import KosCaptureApp


def main() -> None:
    KosCaptureApp().run()


if __name__ == "__main__":
    main()
