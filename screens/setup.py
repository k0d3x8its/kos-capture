"""
screens/setup.py

Setup screen — first-run config UI and ongoing config editor.

Shown automatically on launch when no config file exists. Also reachable
from the Home screen to update paths.

Collects three values from the user:
    - Proton Drive local path: where rclone syncs Field Notes PDFs
    - KOS vault root:          root of the KOS vault (raw/, wiki/, etc.)
    - Remote path:             subfolder on the Proton Drive remote to sync
                               (e.g. Photos/Field-Notes)

Local paths are validated on disk before writing. Remote path is checked
for non-empty only — no network call at setup time.

On success: writes ~/.config/kos-capture/config.toml and switches to Home.
On failure: displays all validation errors inline without clearing inputs.
"""

import core.config as config
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static


class SetupScreen(Screen):

    BINDINGS = [
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

    .field-hint {
        color: $text-muted;
        height: 1;
        padding: 0;
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
                "Enter the paths KOS Capture needs to run.",
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

            yield Label("Remote path on Proton Drive", classes="field-label")
            yield Static("Subfolder to sync, e.g.  Photos/Field-Notes", classes="field-hint")
            yield Input(
                placeholder="Photos/Field-Notes",
                id="remote-path",
            )

            yield Static("", id="errors")
            yield Button("Save", id="save-btn", variant="primary")

    def on_mount(self) -> None:
        if config.exists():
            try:
                cfg = config.load()
                self.query_one("#proton-drive", Input).value = str(cfg.proton_drive)
                self.query_one("#vault-root", Input).value = str(cfg.vault_root)
                self.query_one("#remote-path", Input).value = cfg.remote_path
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save()

    def action_go_back(self) -> None:
        if config.exists():
            self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._save()

    def _save(self) -> None:
        proton = self.query_one("#proton-drive", Input).value.strip()
        vault = self.query_one("#vault-root", Input).value.strip()
        remote = self.query_one("#remote-path", Input).value.strip()
        errors_widget = self.query_one("#errors", Static)

        if not proton or not vault or not remote:
            errors_widget.update("All three fields are required.")
            return

        errors = config.validate(proton, vault, remote)
        if errors:
            errors_widget.update("\n".join(errors))
            return

        config.write(proton, vault, remote)
        self.app.switch_screen("home")
