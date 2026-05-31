# Changelog

## [Unreleased]

## v1.1.0 (2026-05-24)

Full IngestScreen implementation — drives `claude` CLI in stream-JSON mode, renders live output as syntax-highlighted Rich log, and supports bidirectional user input mid-session. Ready screen navigation and escape-guard bugs fixed. Test suite expanded to cover logic paths, not just rendered outcomes.

- **➕:** `screens/ingest.py` — IngestScreen spawns `claude --print --input-format stream-json --output-format stream-json --verbose` with `cwd=vault_root`; sends `/kos-ingest` as first JSON user message; streams stdout JSON events and routes by block type: `text` blocks → Rich-formatted prose lines, `tool_use` blocks → dim cyan tool-call summaries, `tool_result` blocks → green/red result lines, `result` with `is_error=true` → full red error; input bar stays live throughout so the user can reply to Claude mid-session; replies are serialized back to claude's stdin as JSON user messages (plain text as `{"type":"text"}`, tool-result responses as `{"type":"tool_result","tool_use_id":...}`)
- **➕:** `screens/ingest.py` — `_fmt_ingest_line()` pipeline: write verbs (`Wrote`, `Created`, `Updated` …) → green; read verbs (`Reading`, `Scanning`, `Fetching` …) → dim cyan; `**Warning:**` prefix → bold red + dark-red body; `### Heading - subtitle` markdown headings → purple label + dim separator + powder-blue (`#A8D8EA`) subtitle; bare `Title - subtitle` lines → same two-tone coloring; numbered list items (`1.`, `2.` …) → bold purple digit + dim period, always applied before question-mark detection; lines ending in `?` → bright orange; backtick code spans → light-blue text on dark-navy background (`#9CDCFE on #1E2832`); file paths truncated to vault-root-relative display; dates highlighted; default prose → `#F4A261` orange
- **➕:** `screens/ingest.py` — markdown table rendering: `|`-prefixed lines buffered in `_run_ingest`; flushed as `rich.table.Table` (SIMPLE_HEAD box, purple headers, orange cells) via `_log_table()`; separator rows detected and excluded from data; falls back to plain lines if parse fails
- **➕:** `screens/ingest.py` — path display: module-level `_vault_root_display` set by `_begin()` via `global`; `_truncate_to_vault()` strips everything above vault parent so log shows `vault/raw/…` not `/home/user/…`
- **🐞🛠️:** `screens/ingest.py` — Escape blocked while `_ingesting=True` even after turn completes and Run Again button appears; fixed by checking `query_one("#run-again-btn").display` inside `action_go_back()` — escape allowed when Run Again is visible
- **🐞🛠️:** `screens/ready.py` — More Files from Inbox button routed to `"home"` instead of `"inbox"`; corrected to `switch_screen("inbox")`
- **⬆️:** `tests/test_ingest_screen.py` — 1 262-line test file covering: regex group structure (`_TITLE_HYPHEN_RE` alt-1 vs alt-2 group assignment), `_send_user_input` JSON payload format (plain text vs tool-result), `_show_question` behavior, `on_unmount` process cleanup (`terminate()` + `stdin.close()`), `_render_md_table` column count and separator detection, `_apply_code_highlights` span count, `action_go_back` escape-guard logic, screen render and button presence integration tests
- **⬆️:** `tests/test_ready_screen.py` — `test_ready_more_files_btn_goes_inbox` corrected assertion from HomeScreen → InboxScreen; `test_start_ingest_config_error_shows_notification` and `test_start_ingest_config_error_stays_on_ready` added for `_start_ingest()` exception path
- **⬆️:** `tests/test_home_screen.py` — `_status_line()` pure-function unit tests added (checkmark/cross presence, color markup); `action_go_ready` tests added for empty `session_results` (warning toast) and non-empty (navigates to ReadyScreen); `_on_error_modal_dismiss(None)` test verifies HomeScreen stays active

## v1.0.0 (2026-05-21)

UI consistency and navigation polish pass — all screens now share a coherent navigation model, Ready screen groups results by category, and the full session flow (Inbox → Wizard → Ready → Home, Transcribe → Ready → Home) is exercised end-to-end by the test suite.

- **⬆️:** `screens/home.py` — View Results (`v`) added to nav menu and BINDINGS; `action_go_ready` switches to a fresh `ReadyScreen()` instance when `session_results` is non-empty; shows a warning toast when empty so the user knows why nothing happened
- **⬆️:** `screens/inbox.py` — renamed `action_view_summary` → `action_view_results` and binding label to "View Results" throughout; session notice hint updated to `[v] View Results`; both `on_key` handler and action now switch to `ReadyScreen()` instance (bypasses Textual's named-screen cache to guarantee fresh render)
- **⬆️:** `screens/ready.py` — results grouped by source category with bold green headers (`Field Logs`, `Field Research`, `Field Studies`, `Meetings`, `YouTube`, `Podcasts`); `_categorize()` routes by path structure with `_KNOWN_CATEGORIES` guard so unknown paths fall to `Other` instead of being silently dropped; `_fmt_entry()` shows volume name for PDFs and `transcripts/<type>/<date>` for transcripts; `#file-log` `max-height` raised from 12 → 15 and scrolls internally so the terminal window stays still as the list grows; Escape now navigates to Home (was Inbox)
- **🐞🛠️:** `screens/ready.py` — first item only appeared on repeat visits: Textual caches named screens so `RichLog.clear()` + `write()` on a stale instance didn't re-render reliably. Fixed by switching all callers (`home`, `inbox`, `wizard`, `transcribe`) to pass a fresh `ReadyScreen()` instance instead of the `"ready"` string key
- **⬆️:** `screens/setup.py` — Footer added; Back binding made visible in footer; `ctrl+s` binding added (`action_save_config` delegates to `_save()`) so users can save without reaching for the Save button
- **⬆️:** `screens/wizard.py` — Footer added; Back binding made visible; hint text markup fixed (`\\[Enter]` / `\\[Esc]` → renders as literal brackets); `_confirm_move` switches to `ReadyScreen()` instead of `pop_screen()` so the processed PDF appears in the session list immediately
- **⬆️:** `tests/test_home_screen.py` — nav item count updated from 6 → 7; cursor `down` counts incremented for Config and Refresh item navigation tests
- **⬆️:** `tests/test_inbox_screen.py` — `test_view_summary_*` renamed to `test_view_results_*`
- **⬆️:** `tests/test_ready_screen.py` — `test_ready_log_header_precedes_items` added: populates four categories, asserts each header precedes its items in `log.lines` and category order matches `_CATEGORY_ORDER`; `test_ready_escape_preserves_results_and_goes_home` updated (was asserting Inbox, now Home)
- **⬆️:** `tests/test_wizard_screen.py` — `test_confirm_move_switches_to_ready` replaces `test_confirm_move_pops_screen`; asserts `ReadyScreen` is active after confirm and `session_results` contains the moved path

## v0.9.0 (2026-05-20)

Full TranscribeScreen implementation with live progress, download bar, and on-show state reset. `core/transcribe` upgraded with per-segment and per-download progress callbacks, local-file podcast routing, and auto-title derivation.

- **➕:** `screens/transcribe.py` — full rewrite from stub: two-step flow (source type → input/begin → running); `_SOURCES` list (`Proton Meet`, `YouTube`, `Podcast`); per-source placeholder and title-placeholder text; `_begin()` validates local paths before launching worker; `@work(thread=True)` worker streams `on_progress` messages to `RichLog` and fires `on_pct` / `on_dl_pct` callbacks to update `ProgressBar` widgets; download bar (`#run-dl-progress`) shown only for URL sources (YouTube always, Podcast when input starts with `http`); `on_show` resets to step-source when not transcribing via `call_after_refresh`; Escape during transcription fires a warning toast instead of stale inline text; success switches to a fresh `ReadyScreen()` instance
- **⬆️:** `core/transcribe.py` — `_is_url()` helper extracted and used throughout; `run()` now accepts `on_progress`, `on_pct`, `on_dl_pct`, `on_transcribing` callbacks for live UI updates; `title` parameter made optional — auto-derived from filename stem (local) or yt-dlp `info["title"]` (URL); `_transcribe_audio()` accepts `on_pct` and fires it per segment using `seg.end / info.duration`; `_download_audio()` accepts `on_dl_pct` and fires it from the yt-dlp progress hook; local-file podcast routing added — podcasts with a non-URL source skip yt-dlp and pass the file directly to faster-whisper; `run()` routes on `use_url` flag rather than `source_type` alone
- **➕:** `app.py` — `clipboard` property: tries `wl-paste --no-newline` (Wayland), then `xclip`, then `xsel` in order; returns empty string on total failure; avoids hardcoding a single clipboard backend
- **➕:** `tests/test_transcribe_screen.py` — 27 Pilot integration tests: renders, source selection advances to input step, each source sets correct `_source_type`, Escape on source returns to Home, Escape on input returns to source, begin validation (empty input, missing file, no config), begin launches worker, on-show resets to source step, title field optional, `on_pct` / `on_dl_pct` callbacks fire during worker, download bar visibility for all four source-path combinations
- **⬆️:** `tests/test_transcribe.py` — `test_on_pct_called_per_segment` and `test_on_pct_not_called_when_duration_zero` added; title auto-derivation tests added for local-file and URL paths; `run()` signature updated throughout for optional `title` and new callback params
- **⬆️:** `tests/test_wizard_screen.py` — `-under` and `-flip` suffix selection tests added

## v0.8.0 (2026-05-19)

- **🐞🛠️:** `screens/inbox.py` — session notice disappeared on refresh: `_load()` had early-return paths inside `_scan_and_display()` that skipped the notice update entirely. Fixed by splitting `_load()` into sequential `_scan_and_display()` + `_update_notice()` calls so the notice always re-renders regardless of config or folder state
- **⬆️:** `screens/inbox.py` — `on_key` v handler added alongside the existing priority binding as belt-and-suspenders; Textual's binding dispatch can lose priority bindings when focus is inside a deeply nested widget — `on_key` with `event.stop()` guarantees the key is captured
- **🐞🛠️:** `screens/ready.py` — `session_results` cleared silently on Done: `_populate_log()` called `done-btn.focus()` at the end; user pressing Enter on `RichLog` (unfocused, no-op) then Tab cycled focus to Done, and Enter fired Done which called `_finish()` and wiped the session. Fixed by removing `done-btn.focus()` and eliminating `_finish()` — Done now calls `switch_screen("home")` with no side effects
- **🐞🛠️:** `screens/ready.py` — ReadyScreen showed stale log on re-entry: Textual caches screen instances after first push; `on_mount` only fires once. Fixed by adding `on_show` that calls `_populate_log()` each time the screen becomes active
- **⬆️:** `screens/ready.py` — `session_results` persists for the full app run; clearing only happens on app restart via `app.on_mount`. "Done" is now a non-destructive navigation — "View Summary" remains reachable from Inbox throughout the session even after hitting Done
- **⬆️:** `screens/wizard.py` — layout aligned `center top` with `padding: 1 0` to match ReadyScreen; `ContentSwitcher` given `max-height: 12`; `#errors` widget moved above `ContentSwitcher` so errors are always visible at a stable position regardless of which step is active; `_focus_step()` resets ListView `index` to 0 via `set_timer` on each step transition to clear stale cursor state
- **➕:** `tests/test_ready_screen.py` — 8 Pilot integration tests: renders with results, plural title, file paths written to RichLog, ingest command widget present, Done navigates home and preserves `session_results`, Escape navigates to Inbox and preserves `session_results`, empty results renders without crash, `on_show` re-populates log when new results added after first visit
- **⬆️:** `tests/test_inbox_screen.py` — session notice tests added: hidden when no results, shown with count and `[v]` hint when results exist, `v` key navigates to ReadyScreen, `v` noop when no results; regression test `test_session_notice_survives_refresh_with_no_config` verifies notice persists after `r` when config is absent
- **🐞🛠️:** `tests/test_sync_screen.py` — `test_no_config_shows_error` used `pilot.click("#trigger-btn")` on an unfocused button; SyncScreen focuses RichLog on mount so the click was silently ignored. Fixed with `Button.press()` to match all other sync tests

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
