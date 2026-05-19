# Changelog

## v0.7.0 (2026-05-18)

- **➕:** `screens/inbox.py` — PDF Inbox screen: flat scan of `proton_drive` for PDFs sorted newest-first by mtime; ListView with filename, size, and modified date; count display (`N PDFs ready to process`); empty-state and config-missing guards; `r` refreshes without leaving screen; Enter on a file pushes WizardScreen with the selected path; Escape returns to Home
- **🐞🛠️:** `screens/inbox.py` — refresh crash fixed: `ListView.clear()` is async — calling without `await` in a sync method left old items in the DOM when new items with the same IDs were appended (`DuplicateIds`). Fixed by dropping IDs from ListItems entirely and using `ListView.index` for selection lookup instead
- **⬆️:** `screens/wizard.py` — stub updated to accept `file_path: Path` parameter from InboxScreen; Escape binding added with `pop_screen()` to return to Inbox
- **➕:** `tests/test_inbox_screen.py` — 12 tests: `_format_size` unit tests, `_scan_pdfs` unit tests (PDF-only filter, newest-first sort, missing folder), screen integration tests (no-config guard, empty folder, PDF list, count display, refresh rescans, escape navigation)

## v0.6.0 (2026-05-18)

- **➕:** `screens/sync.py` — full SyncScreen implementation: rclone installed / timer active / last sync status panel; manual sync trigger button; background `@work(thread=True)` worker streams rclone stdout line-by-line into RichLog; button disabled during sync; Escape blocked while sync is running with yellow warning; status auto-refreshes on completion; success text uses `#00ff41` to match primary button color
- **🐞🛠️:** `screens/sync.py` — `self.call_from_thread` replaced with `self.app.call_from_thread`; `call_from_thread` is an App method, not a Screen method — caused `AttributeError` when worker tried to update the UI
- **⬆️:** `screens/sync.py` — rclone output switched from `--progress` to `--verbose` for clean per-file log lines; `--progress` uses ANSI escape codes that corrupt RichLog display; `wrap=True` added to RichLog to contain long output lines
- **➕:** `tests/test_sync_screen.py` — 10 tests: renders, status display, button disabled during sync, sync-complete callbacks (exit 0 and non-zero), escape blocked during sync, escape allowed when idle
- **⬆️:** `core/rclone.py` — `trigger_sync` updated: accepts `remote_path` param; builds `proton:{remote_path}` as scoped source instead of syncing the remote root; switched from `rclone sync` to `rclone copy` (copy never deletes local files regardless of remote state); switched from `--progress` to `--verbose`
- **🐞🛠️:** `core/rclone.py` — remote name corrected from `protondrive:` to `proton:` to match system rclone config
- **➕:** `core/config.py` — `remote_path: str` field added to Config dataclass; stores Proton Drive subfolder for scoped sync (e.g. `Photos/Field-Notes`); `validate()` and `write()` updated to accept and persist all three fields
- **🐞🛠️:** `core/config.py` — `validate()` and `write()` now call `.expanduser()` before filesystem checks so `~` in user-typed paths resolves correctly instead of returning false negatives
- **⬆️:** `screens/setup.py` — `#remote-path` Input added for Proton Drive subfolder; `_save()` reads, validates, and writes all three fields
- **⬆️:** `tests/test_config.py` — updated for three-field config; `validate()` and `write()` calls updated throughout; `remote_path` assertions added; tilde-expansion tests added
- **⬆️:** `tests/test_rclone.py` — `test_trigger_sync_builds_correct_command` updated to assert `args[1] == "copy"` and `args[2] == "proton:Photos/Field-Notes"`; `test_trigger_sync_strips_leading_slash` added
- **⬆️:** `tests/test_setup_screen.py` — updated for three-field form; `#remote-path` input added to all multi-field tests; `pilot.click("#save-btn")` replaced with `Button.press()` (button scrolls off viewport in taller panel, `OutOfBounds` fix)

## v0.5.0 (2026-05-18)

- **➕:** `screens/home.py` — full HomeScreen: ASCII banner (`KOS` via `ansi_shadow` + `Capture` via `calvin_s`), centered `ListView` nav menu with double border and `Main Menu` title with separator line, compact system-status panel below; letter shortcuts (`s`, `i`, `t`, `c`, `r`) and arrow+Enter navigation both supported; `on_list_view_selected` dispatches to the same actions as letter bindings
- **⬆️:** `screens/home.py` — nav items padded to equal length (16 chars) via variable dashes so `text-align: center` aligns uniformly; `\[x]` Rich escape renders literal bracket-letter shortcut labels; nav-panel and status-panel both wrapped in `Center()` containers to align with ASCII banner
- **➕:** `tests/test_home_screen.py` — 9 tests: renders, ASCII banner present, status panel present, letter shortcuts dispatch correctly, arrow+Enter nav via `ListView.Selected`, status panel updates on refresh

## v0.4.0 (2026-05-18)

- **➕:** `screens/setup.py` — first-run config form: Proton Drive local path, KOS vault root, Proton Drive remote subfolder; validates all fields with `config.validate()` before writing; errors displayed inline; Escape returns to Home without saving
- **⬆️:** `app.py` — terminal-green theme registered and applied on mount (`primary: #00ff41`, `background: #000000`); initial routing moved to `app.on_mount` — checks `config.exists()` and pushes `setup` or `home` accordingly
- **⬆️:** `main.py` — simplified to single `KosCaptureApp().run()` call; routing logic moved to `app.on_mount`
- **➕:** `pytest.ini` — `asyncio_mode = auto` for Textual Pilot tests
- **➕:** `tests/test_setup_screen.py` — 4 Pilot integration tests: renders, empty-inputs error, invalid-path error, valid inputs call `config.write()`
- **⬆️:** `tests/test_app.py` — theme registration, screen registry, and `on_mount` routing assertions added
- **⬆️:** `tests/test_main.py` — updated to reflect simplified `main()` entry point

## v0.3.0 (2026-05-18)

- **➕:** `app.py` — `KosCaptureApp` with named SCREENS registry (`home`, `setup`, `sync`, `inbox`, `wizard`, `transcribe`, `ready`), global `ctrl+q` quit binding, top-level letter shortcuts (`h`, `s`, `i`, `t`)
- **➕:** `main.py` — entry point with config-gate routing: pushes `setup` on first run, `home` on subsequent runs
- **➕:** `screens/home.py`, `screens/setup.py`, `screens/sync.py`, `screens/inbox.py`, `screens/wizard.py`, `screens/transcribe.py`, `screens/ready.py` — minimal Screen stubs
- **➕:** `tests/test_app.py` — screen registry and keybinding checks
- **➕:** `tests/test_main.py` — config gate routing checks

## v0.2.0 (2026-05-18)

- **➕:** `core/config.py` — read/write `~/.config/kos-capture/config.toml`; `Config` dataclass (`proton_drive`, `vault_root`, `remote_path`); `exists()`, `load()`, `validate()`, `write()`
- **➕:** `core/rclone.py` — `RcloneStatus` dataclass; `is_installed()`, `timer_active()`, `last_sync_time()`, `status()`, `trigger_sync()`; systemd `LastTriggerUSec` parser; all subprocess calls wrapped
- **➕:** `core/vault.py` — volume detection in `raw/Field-Logs/`, `raw/Field-Research/`, `raw/Field-Studies/`; new volume directory creation; three collections hardcoded per KOS schema
- **➕:** `core/transcribe.py` — `faster-whisper` wrapper with `yt-dlp` audio download for YouTube/Podcast sources; `[MM:SS]` timestamped `.md` output; `YYYY-MM-DD` filename prefix; local-only, no external services
- **➕:** `tests/test_config.py` — config read/write/validate unit tests
- **➕:** `tests/test_rclone.py` — rclone wrapper unit tests; all subprocess calls mocked
- **➕:** `tests/test_vault.py` — vault path helper unit tests
- **➕:** `tests/test_transcribe.py` — transcribe wrapper unit tests

## v0.1.0 (2026-05-18)

- **➕:** Initial project scaffold — `k0d3x8its/kos-capture` repository created
- **➕:** `requirements.txt` — `textual`, `pyfiglet`, `tomli`, `faster-whisper`, `yt-dlp`, `pytest-asyncio`
- **➕:** `README.md` — project overview, pipeline diagrams, prerequisites, install and run instructions, screen reference, repo structure
- **➕:** `.github/workflows/ci.yml` — CI pipeline
- **➕:** `.gitignore`

---

# Glossary

**ADDED** = ➕ **|**
**REMOVED** = ❌ **|**
**FIXED** = 🛠️ **|**
**BUG** = 🐞 **|**
**IMPROVED** = 🚀 **|**
**CHANGED** = ♻️ **|**
**SECURITY** = 🛡️ **|**
**DEPRECATED** = ⚠️ **|**
**UPDATED** = ⬆️
