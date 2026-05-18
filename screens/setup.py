"""
screens/setup.py

Setup screen — first-run config UI and ongoing config editor.

Shown automatically on launch when no config file exists (routed from
main.py). Also reachable from the Home screen when the user wants to
update their paths.

Collects two paths from the user:
    - Proton Drive local path: where rclone syncs Field Notes PDFs
    - KOS vault root: root of the KOS vault (contains raw/, wiki/, etc.)

Both paths are validated on disk before writing. No defaults — the user
must supply real paths that exist on their machine.

On success: writes ~/.config/kos-capture/config.toml and switches to Home.
On failure: displays all validation errors inline without clearing the inputs.
"""

import core.config as config
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static


class SetupScreen(Screen):

    BINDINGS = [
        # Escape only goes back when re-configuring — on first run there is
        # no previous screen to return to, so pressing Escape does nothing.
        Binding("escape", "go_back", "Back", show=False),
    ]

    DEFAULT_CSS = """
    SetupScreen {
        align: center middle;
    }

    #panel {
        width: 64;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    .field-label {
        margin-top: 1;
    }

    #errors {
        color: $error;
        margin-top: 1;
        height: auto;
    }

    #save-btn {
        margin-top: 2;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static("KOS Capture — Setup", id="title")
            yield Static(
                "Enter the two paths KOS Capture needs to run.",
                id="subtitle",
            )

            yield Label("Proton Drive local path", classes="field-label")
            yield Input(
                placeholder="/home/user/ProtonDrive/Scans",
                id="proton-drive",
            )

            yield Label("KOS vault root", classes="field-label")
            yield Input(
                placeholder="/home/user/my-kos-vault",
                id="vault-root",
            )

            # Error area is empty until validation fails
            yield Static("", id="errors")

            yield Button("Save", id="save-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save()

    def action_go_back(self) -> None:
        """Pop back to Home — only valid when re-configuring, not first run."""
        if config.exists():
            self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Allow pressing Enter in either input field to trigger save."""
        self._save()

    def _save(self) -> None:
        """Validate inputs and write config, or surface errors inline."""
        proton = self.query_one("#proton-drive", Input).value.strip()
        vault = self.query_one("#vault-root", Input).value.strip()
        errors_widget = self.query_one("#errors", Static)

        # Catch empty inputs before hitting the filesystem
        if not proton or not vault:
            errors_widget.update("Both paths are required.")
            return

        errors = config.validate(proton, vault)
        if errors:
            errors_widget.update("\n".join(errors))
            return

        config.write(proton, vault)
        # Replace setup with home — works for both first-run and re-config
        self.app.switch_screen("home")
