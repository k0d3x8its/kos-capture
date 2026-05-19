"""
screens/wizard.py

Naming Wizard — four-step flow for processing a single PDF from the Inbox.

Steps:
  1. suffix     — bare (no suffix), -sticky, -under, -flip
  2. collection — Field-Logs, Field-Research, Field-Studies
  3. volume     — existing volumes from the vault, or "+ New volume"
  3b. new-volume — name the new volume and create it
  4. confirm    — preview the destination path; move on confirm

On confirm: the PDF is renamed with the chosen suffix and moved into
vault_root/raw/{collection}/{volume}/. The destination path is appended
to app.session_results so ReadyScreen can display it. A success toast
fires and the screen pops back to Inbox.

Escape navigates one step backward; on the first step it pops to Inbox.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import core.config as config
import core.vault as vault
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, ContentSwitcher, Input, Label, ListItem, ListView, Static


_SUFFIXES: list[tuple[str, str]] = [
    ("bare  (no suffix)", ""),
    ("-sticky", "-sticky"),
    ("-under", "-under"),
    ("-flip", "-flip"),
]

_COLLECTION_PREFIX: dict[str, str] = {
    "Field-Logs":     "FL",
    "Field-Research": "FR",
    "Field-Studies":  "FS",
}

_STEP_LABELS: dict[str, str] = {
    "step-suffix":     "Step 1 of 4 — Choose suffix",
    "step-collection": "Step 2 of 4 — Choose collection",
    "step-volume":     "Step 3 of 4 — Choose volume",
    "step-new-volume": "Step 3 of 4 — Name new volume",
    "step-confirm":    "Step 4 of 4 — Confirm move",
}

_NEW_VOLUME_LABEL = "+ New volume"


class WizardScreen(Screen):

    BINDINGS = [Binding("escape", "go_back", "Back", show=False)]

    DEFAULT_CSS = """
    WizardScreen {
        align: center middle;
    }

    #panel {
        width: 72;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 0;
    }

    #filename {
        text-align: center;
        color: $text-muted;
        height: 1;
        margin-bottom: 1;
    }

    #step-label {
        color: $primary;
        text-style: bold;
        height: 1;
        margin-bottom: 1;
    }

    ContentSwitcher {
        height: auto;
    }

    .choice-list {
        height: auto;
        max-height: 10;
        border: round $panel;
        background: transparent;
        padding: 0 1;
        margin-bottom: 1;
    }

    .choice-list > ListItem {
        background: transparent;
        height: 1;
        padding: 0;
    }

    #panel .choice-list > ListItem.-highlight {
        background: transparent;
    }

    .choice-list > ListItem > Label {
        width: 100%;
        color: $text-muted;
    }

    #panel .choice-list > ListItem.-highlight > Label {
        color: #00ff00;
        text-style: bold;
    }

    #dest-label {
        color: $text-muted;
        height: 1;
    }

    #dest-path {
        color: $primary;
        height: auto;
        margin-bottom: 1;
    }

    #confirm-btn, #new-vol-btn {
        width: 100%;
        margin-top: 1;
    }

    #errors {
        color: $error;
        height: auto;
        margin-top: 1;
    }

    #hint {
        color: $text-muted;
        text-align: center;
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(self, file_path: Path) -> None:
        super().__init__()
        self.file_path = file_path
        self._suffix = ""
        self._collection = ""
        self._volume = ""
        self._vault_root: Path | None = None
        self._volume_items: list[str] = []
        self._step = "step-suffix"

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static("KOS Capture — Naming Wizard", id="title")
            yield Static(self.file_path.name, id="filename")
            yield Static("", id="step-label")
            with ContentSwitcher(initial="step-suffix", id="switcher"):
                with Vertical(id="step-suffix"):
                    yield ListView(
                        *[ListItem(Label(label)) for label, _ in _SUFFIXES],
                        id="suffix-list",
                        classes="choice-list",
                    )
                with Vertical(id="step-collection"):
                    yield ListView(
                        *[ListItem(Label(c)) for c in vault.COLLECTIONS],
                        id="collection-list",
                        classes="choice-list",
                    )
                with Vertical(id="step-volume"):
                    yield ListView(id="volume-list", classes="choice-list")
                with Vertical(id="step-new-volume"):
                    yield Input(placeholder="e.g. FL-vol-001", id="new-vol-input")
                    yield Button(
                        "Create volume & continue", id="new-vol-btn", variant="primary"
                    )
                with Vertical(id="step-confirm"):
                    yield Static("Destination:", id="dest-label")
                    yield Static("", id="dest-path")
                    yield Button("Move file →", id="confirm-btn", variant="primary")
            yield Static("", id="errors")
            yield Static("[Enter] select  ·  [Esc] back", id="hint")

    def on_mount(self) -> None:
        self._update_step_label()
        self._focus_step()
        if config.exists():
            try:
                cfg = config.load()
                self._vault_root = cfg.vault_root
            except Exception as exc:
                self.query_one("#errors", Static).update(
                    f"[red]Config error: {exc}[/red]"
                )

    # ── Step helpers ────────────────────────────────────────────────────────

    def _update_step_label(self) -> None:
        self.query_one("#step-label", Static).update(_STEP_LABELS[self._step])

    def _go_to(self, step: str) -> None:
        self._step = step
        self._update_step_label()
        self.query_one("#errors", Static).update("")
        self.query_one(ContentSwitcher).current = step
        self._focus_step()

    _STEP_FOCUS: dict[str, str] = {
        "step-suffix":     "#suffix-list",
        "step-collection": "#collection-list",
        "step-volume":     "#volume-list",
        "step-new-volume": "#new-vol-input",
        "step-confirm":    "#confirm-btn",
    }

    def _focus_step(self) -> None:
        selector = self._STEP_FOCUS.get(self._step)
        if selector:
            try:
                self.query_one(selector).focus()
            except Exception:
                pass

    # ── Navigation ──────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        prev: dict[str, str | None] = {
            "step-suffix":     None,
            "step-collection": "step-suffix",
            "step-volume":     "step-collection",
            "step-new-volume": "step-volume",
            "step-confirm":    "step-volume",
        }
        previous = prev.get(self._step)
        if previous is None:
            self.app.pop_screen()
        else:
            self._go_to(previous)

    # ── List selection ──────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = event.list_view
        idx = lv.index
        if idx is None:
            return

        if lv.id == "suffix-list" and idx < len(_SUFFIXES):
            self._suffix = _SUFFIXES[idx][1]
            self._go_to("step-collection")

        elif lv.id == "collection-list" and idx < len(vault.COLLECTIONS):
            self._collection = vault.COLLECTIONS[idx]
            self._populate_volumes()
            self._go_to("step-volume")

        elif lv.id == "volume-list" and idx < len(self._volume_items):
            selected = self._volume_items[idx]
            if selected == _NEW_VOLUME_LABEL:
                prefix = _COLLECTION_PREFIX.get(self._collection, "")
                self.query_one("#new-vol-input", Input).placeholder = (
                    f"e.g. {prefix}-vol-001" if prefix else "e.g. vol-001"
                )
                self.query_one("#new-vol-input", Input).value = ""
                self._go_to("step-new-volume")
            else:
                self._volume = selected
                self._build_confirm()
                self._go_to("step-confirm")

    def _populate_volumes(self) -> None:
        lv = self.query_one("#volume-list", ListView)
        lv.clear()
        self._volume_items = []
        if self._vault_root:
            for name in vault.volumes(self._vault_root, self._collection):
                lv.append(ListItem(Label(name)))
                self._volume_items.append(name)
        lv.append(ListItem(Label(_NEW_VOLUME_LABEL)))
        self._volume_items.append(_NEW_VOLUME_LABEL)
        lv.index = 0

    def _build_confirm(self) -> None:
        new_name = f"{self.file_path.stem}{self._suffix}.pdf"
        if self._vault_root:
            dest = (
                vault.volume_path(self._vault_root, self._collection, self._volume)
                / new_name
            )
            self.query_one("#dest-path", Static).update(str(dest))
        else:
            self.query_one("#dest-path", Static).update(
                "[red]No vault root configured.[/red]"
            )

    # ── Button / input handlers ─────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new-vol-btn":
            self._handle_new_volume()
        elif event.button.id == "confirm-btn":
            self._confirm_move()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "new-vol-input":
            self._handle_new_volume()

    def _handle_new_volume(self) -> None:
        name = self.query_one("#new-vol-input", Input).value.strip()
        errors = self.query_one("#errors", Static)
        if not name:
            errors.update("[red]Volume name is required.[/red]")
            return
        if "/" in name or ".." in name:
            errors.update("[red]Volume name must not contain / or ..[/red]")
            return
        if self._vault_root:
            vault.create_volume(self._vault_root, self._collection, name)
        self._volume = name
        self._build_confirm()
        self._go_to("step-confirm")

    def _confirm_move(self) -> None:
        errors = self.query_one("#errors", Static)
        if not self._vault_root:
            errors.update("[red]No vault root — return to Setup.[/red]")
            return
        new_name = f"{self.file_path.stem}{self._suffix}.pdf"
        dest_dir = vault.volume_path(self._vault_root, self._collection, self._volume)
        dest = dest_dir / new_name
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(self.file_path), str(dest))
        except Exception as exc:
            errors.update(f"[red]Move failed: {exc}[/red]")
            return
        self.app.session_results.append(dest)
        self.app.pop_screen()
        self.app.notify(f"Moved → {dest.name}", severity="information")
