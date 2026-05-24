"""
tests/test_ingest_screen.py

Unit and integration tests for screens/ingest.py.

Subprocess spawning is mocked in all integration tests — no real claude
process is started. Pure-function tests (_strip_ansi, _fmt_ingest_line,
_fmt_tool_use) run without any mocking.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import Button, Input, RichLog, Static

from app import KosCaptureApp
import json

import screens.ingest as _ingest_mod
from screens.ingest import (
    IngestScreen,
    _apply_code_highlights,
    _apply_date_highlights,
    _apply_inline_md,
    _apply_path_highlights,
    _fmt_ingest_line,
    _fmt_tool_use,
    _fmt_tool_use_rich,
    _render_md_table,
    _strip_ansi,
    _truncate_to_vault,
    _CODE_SPAN_RE,
    _DATE_RE,
    _MD_HEADING_RE,
    _NUM_LIST_RE,
    _TITLE_HYPHEN_RE,
    _WARN_MD_RE,
)


# ── _strip_ansi() ─────────────────────────────────────────────────────────────

def test_strip_ansi_removes_color_codes():
    assert _strip_ansi("\x1b[32mHello\x1b[0m") == "Hello"


def test_strip_ansi_removes_cursor_movement():
    assert _strip_ansi("\x1b[2J\x1b[H") == ""


def test_strip_ansi_removes_carriage_return():
    assert _strip_ansi("Hello\rWorld") == "HelloWorld"


def test_strip_ansi_keeps_plain_content():
    assert _strip_ansi("plain text") == "plain text"


def test_strip_ansi_osc_sequence():
    assert _strip_ansi("\x1b]0;title\x07text") == "text"


def test_strip_ansi_bold_sequence():
    assert _strip_ansi("\x1b[1mBold\x1b[0m") == "Bold"


# ── _fmt_ingest_line() ────────────────────────────────────────────────────────

def test_fmt_ingest_line_write_action():
    out = _fmt_ingest_line("Wrote wiki/sources/FL-vol-001.md")
    assert "[green]" in out
    assert "Wrote wiki/sources/FL-vol-001.md" in out


def test_fmt_ingest_line_created_action():
    out = _fmt_ingest_line("Created wiki/books/FL-vol-001.md")
    assert "[green]" in out


def test_fmt_ingest_line_read_action():
    out = _fmt_ingest_line("Reading raw/Field-Logs/FL-vol-001/page.pdf")
    assert "[dim cyan]" in out


def test_fmt_ingest_line_searching_action():
    out = _fmt_ingest_line("Searching for existing wiki entries…")
    assert "[dim cyan]" in out


def test_fmt_ingest_line_error():
    out = _fmt_ingest_line("Error: file not found")
    assert "[red]" in out


def test_fmt_ingest_line_warning():
    out = _fmt_ingest_line("Warning: missing frontmatter in note.md")
    assert "[red]" in out


def test_fmt_ingest_line_failed():
    out = _fmt_ingest_line("Failed to parse PDF")
    assert "[red]" in out


def test_fmt_ingest_line_question_bright_orange():
    """Lines ending with '?' render in bright orange to pop."""
    out = _fmt_ingest_line("Which volume should I assign this to?")
    assert "#FF6B35" in out


def test_fmt_ingest_line_prose_light_orange():
    """Non-action prose (no question mark) renders in light orange."""
    out = _fmt_ingest_line("I found 3 pages — creating FL-vol-002 entry.")
    assert "#F4A261" in out
    assert "[green]" not in out
    assert "[red]" not in out


def test_fmt_ingest_line_question_with_arrow():
    """Prose ending with '?' gets bright orange even with em-dash."""
    out = _fmt_ingest_line("I found 3 pages — shall I create FL-vol-002?")
    assert "#FF6B35" in out


def test_fmt_ingest_line_bold_md_highlighted():
    """**text** is replaced with bold light-orange markup."""
    out = _fmt_ingest_line("The **Skip** option ignores this file.")
    assert "#F4A261" in out
    assert "Skip" in out
    assert "**" not in out


def test_fmt_ingest_line_numbered_prefix_colored():
    """Lines starting with 'N. ' get the numbered prefix in light orange."""
    out = _fmt_ingest_line("1. Continue with processing")
    assert "#F4A261" in out


def test_apply_inline_md_replaces_bold():
    assert _apply_inline_md("**Skip**") == "[bold #F4A261]Skip[/bold #F4A261]"


def test_apply_inline_md_leaves_plain_text():
    assert _apply_inline_md("plain text") == "plain text"


def test_fmt_ingest_line_write_takes_priority_over_error():
    """Write tier matches before error tier even if line contains 'Error'."""
    out = _fmt_ingest_line("Wrote error_log.md")
    assert "[green]" in out


def test_fmt_ingest_line_escapes_square_brackets():
    """Square brackets that look like Rich markup tags are escaped in AI prose."""
    out = _fmt_ingest_line("Claude says [bold]yes[/bold]")
    # \[ in the returned string proves Rich escape was applied
    assert "\\[bold]" in out


def test_fmt_ingest_line_escapes_brackets_in_write_line():
    """Square brackets inside a write-tier line are also escaped."""
    out = _fmt_ingest_line("Wrote wiki/sources/[draft].md")
    assert "[green]" in out
    assert "\\[draft]" in out or "[draft]" not in out.replace("\\[draft]", "")


# ── _fmt_tool_use() ───────────────────────────────────────────────────────────

def test_fmt_tool_use_read_maps_to_reading():
    assert _fmt_tool_use("Read", {"file_path": "raw/note.pdf"}).startswith("Reading")


def test_fmt_tool_use_write_maps_to_wrote():
    assert _fmt_tool_use("Write", {"file_path": "wiki/out.md"}).startswith("Wrote")


def test_fmt_tool_use_edit_maps_to_editing():
    assert _fmt_tool_use("Edit", {"file_path": "wiki/out.md"}).startswith("Editing")


def test_fmt_tool_use_includes_target():
    out = _fmt_tool_use("Read", {"file_path": "raw/note.pdf"})
    assert "raw/note.pdf" in out


def test_fmt_tool_use_unknown_tool_uses_name():
    out = _fmt_tool_use("CustomTool", {})
    assert "CustomTool" in out


def test_fmt_tool_use_no_target_omits_double_space():
    out = _fmt_tool_use("Bash", {})
    assert out == "Running"


# ── Screen render ─────────────────────────────────────────────────────────────

async def test_ingest_screen_renders(tmp_path):
    """IngestScreen composes without error and key widgets are present."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await pilot.app.push_screen(IngestScreen(tmp_path))
            await pilot.pause()
            screen = pilot.app.screen
            assert screen.query_one("#ingest-log") is not None
            assert screen.query_one("#user-input") is not None
            assert screen.query_one("#send-btn")   is not None
            assert screen.query_one("#status")     is not None


async def test_ingest_input_unlocked_initially(tmp_path):
    """Input and Send button are enabled from the start (always-unlocked design)."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await pilot.app.push_screen(IngestScreen(tmp_path))
            await pilot.pause()
            screen = pilot.app.screen
            assert screen.query_one("#user-input", Input).disabled is False
            assert screen.query_one("#send-btn",   Button).disabled is False


# ── claude not on PATH ────────────────────────────────────────────────────────

async def test_claude_not_found_shows_error(tmp_path):
    """When claude is not on PATH, an error message appears in the log."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await pilot.app.push_screen(IngestScreen(tmp_path))
            await pilot.pause()
            log     = pilot.app.screen.query_one("#ingest-log", RichLog)
            written = "\n".join(str(line) for line in log.lines)
            assert "not found" in written.lower() or "path" in written.lower()


async def test_claude_not_found_ingesting_stays_false(tmp_path):
    """When claude is not on PATH, _ingesting is never set True."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            assert screen._ingesting is False


# ── Escape handling ───────────────────────────────────────────────────────────

async def test_escape_blocked_during_ingest(tmp_path):
    """Escape while actively ingesting (run-again hidden) fires toast and blocks."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._ingesting = True
            screen.query_one("#run-again-btn", Button).display = False
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen is screen


async def test_escape_allowed_after_turn_complete(tmp_path):
    """Escape allowed when run-again is visible (turn done, awaiting reply)."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await pilot.app.push_screen("ready")
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._ingesting = True
            screen.query_one("#run-again-btn", Button).display = True
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "ReadyScreen"


async def test_escape_allowed_when_not_ingesting(tmp_path):
    """Escape when not ingesting pops back to the previous screen (ReadyScreen)."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            await pilot.app.push_screen("ready")
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            assert screen._ingesting is False
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen.__class__.__name__ == "ReadyScreen"


# ── _on_done() ────────────────────────────────────────────────────────────────

async def test_on_done_clears_ingesting_flag(tmp_path):
    """_on_done() sets _ingesting to False."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._ingesting = True
            screen._on_done()
            await pilot.pause()
            assert screen._ingesting is False


async def test_on_done_updates_status(tmp_path):
    """_on_done() updates the status widget to show completion."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._ingesting = True
            screen._on_done()
            await pilot.pause()
            status = str(screen.query_one("#status", Static).content)
            assert "complete" in status.lower()


async def test_on_done_locks_input(tmp_path):
    """_on_done() leaves Input and Send disabled."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            # Simulate input being unlocked mid-session
            screen.query_one("#user-input", Input).disabled = False
            screen.query_one("#send-btn",   Button).disabled = False
            screen._on_done()
            await pilot.pause()
            assert screen.query_one("#user-input", Input).disabled is True
            assert screen.query_one("#send-btn",   Button).disabled is True


# ── Noop key bindings (navigation guard) ──────────────────────────────────────

async def test_t_key_does_not_navigate_away(tmp_path):
    """'t' does not switch to TranscribeScreen while IngestScreen is active."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            await pilot.press("t")
            await pilot.pause()
            assert pilot.app.screen is screen


async def test_h_key_does_not_navigate_away(tmp_path):
    """'h' does not switch to HomeScreen while IngestScreen is active."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            await pilot.press("h")
            await pilot.pause()
            assert pilot.app.screen is screen


async def test_s_key_does_not_navigate_away(tmp_path):
    """'s' does not switch to SyncScreen while IngestScreen is active."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            assert pilot.app.screen is screen


async def test_i_key_does_not_navigate_away(tmp_path):
    """'i' does not switch to InboxScreen while IngestScreen is active."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            await pilot.press("i")
            await pilot.pause()
            assert pilot.app.screen is screen


# ── _fmt_tool_use_rich() ──────────────────────────────────────────────────────

def test_fmt_tool_use_rich_read_dims_directory():
    out = _fmt_tool_use_rich("Read", {"file_path": "raw/Field-Logs/FL-vol-001/note.pdf"})
    assert "[dim cyan]" in out
    assert "raw/Field-Logs/FL-vol-001/" in out


def test_fmt_tool_use_rich_read_brightens_filename():
    out = _fmt_tool_use_rich("Read", {"file_path": "raw/Field-Logs/FL-vol-001/note.pdf"})
    assert "[cyan]" in out
    assert "note.pdf" in out


def test_fmt_tool_use_rich_write_dims_directory():
    out = _fmt_tool_use_rich("Write", {"file_path": "wiki/sources/note.md"})
    assert "[dim green]" in out
    assert "wiki/sources/" in out


def test_fmt_tool_use_rich_write_brightens_filename():
    out = _fmt_tool_use_rich("Write", {"file_path": "wiki/sources/note.md"})
    assert "[bold green]" in out
    assert "note.md" in out


def test_fmt_tool_use_rich_no_path_verb_only():
    out = _fmt_tool_use_rich("Bash", {})
    assert "Running" in out
    assert "Running  " not in out   # no "verb  target" separator when target absent


def test_fmt_tool_use_rich_flat_filename_no_parent():
    out = _fmt_tool_use_rich("Read", {"file_path": "note.pdf"})
    assert "note.pdf" in out
    assert "note.pdf/" not in out   # no spurious dir suffix


# ── **Warning:** formatting ───────────────────────────────────────────────────

def test_fmt_ingest_line_bold_warning_bright_red_title():
    """**Warning:** prefix renders in bold bright red."""
    out = _fmt_ingest_line("**Warning:** Inconsistent frontmatter in FL-vol-001.md")
    assert "#FF1744" in out
    assert "Warning:" in out


def test_fmt_ingest_line_bold_warning_burnt_red_body():
    """Text after **Warning:** renders in burnt red."""
    out = _fmt_ingest_line("**Warning:** Inconsistent frontmatter in FL-vol-001.md")
    assert "#C62828" in out


def test_fmt_ingest_line_bold_warning_no_asterisks():
    """Asterisks are stripped from **Warning:** output."""
    out = _fmt_ingest_line("**Warning:** Something went wrong")
    assert "**" not in out


# ── Date highlighting ─────────────────────────────────────────────────────────

def test_apply_date_highlights_mm_dd_yyyy():
    out = _apply_date_highlights("Logged on 12/25/2024 by field team.")
    assert "[bold #FFD700]12/25/2024[/bold #FFD700]" in out


def test_apply_date_highlights_m_d_yy():
    out = _apply_date_highlights("Entry dated 1/5/24.")
    assert "[bold #FFD700]1/5/24[/bold #FFD700]" in out


def test_apply_date_highlights_no_match_plain_text():
    out = _apply_date_highlights("No dates here.")
    assert "#FFD700" not in out


def test_fmt_ingest_line_prose_date_colored():
    """Dates in Claude prose are colored bright yellow."""
    out = _fmt_ingest_line("Field log entry from 12/25/2024 contains 3 pages.")
    assert "#FFD700" in out


# ────────────────────────────────────────────────────────────────────────────

def test_fmt_ingest_line_plain_warning_still_red():
    """Lines with 'Warning:' (no bold markers) still fall through to [red]."""
    out = _fmt_ingest_line("Warning: missing frontmatter in note.md")
    assert "[red]" in out
    assert "#FF1744" not in out


# ── Token bar ─────────────────────────────────────────────────────────────────

async def test_token_bar_shows_counts_and_cost(tmp_path):
    """_update_token_bar writes token counts and cost to #token-bar."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._update_token_bar(
                {"input_tokens": 1_234, "output_tokens": 567,
                 "cache_read_input_tokens": 89},
                0.0042,
            )
            await pilot.pause()
            bar = str(screen.query_one("#token-bar", Static).content)
            assert "1,234"  in bar
            assert "567"    in bar
            assert "89"     in bar
            assert "0.0042" in bar


async def test_token_bar_omits_cost_when_none(tmp_path):
    """_update_token_bar omits Cost section when cost_usd is None."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._update_token_bar({"input_tokens": 100, "output_tokens": 50}, None)
            await pilot.pause()
            bar = str(screen.query_one("#token-bar", Static).content)
            assert "Cost" not in bar


# ── _apply_path_highlights() ──────────────────────────────────────────────────

def test_apply_path_highlights_dims_directory():
    out = _apply_path_highlights("See wiki/sources/note.md for details.")
    assert "[dim cyan]wiki/sources/[/dim cyan]" in out


def test_apply_path_highlights_brightens_filename():
    out = _apply_path_highlights("See wiki/sources/note.md for details.")
    assert "[bold cyan]note.md[/bold cyan]" in out


def test_apply_path_highlights_no_path_unchanged():
    text = "No paths here at all."
    assert _apply_path_highlights(text) == text


def test_apply_path_highlights_bare_filename_colored():
    """Bare filename with known extension gets bold cyan treatment."""
    out = _apply_path_highlights("Just note.md here.")
    assert "[bold cyan]note.md[/bold cyan]" in out


def test_apply_path_highlights_bare_filename_unknown_ext_no_match():
    """Bare filename with unknown extension is not colored."""
    out = _apply_path_highlights("version 2.5 is out")
    assert "[bold cyan]" not in out


# ── Numbered list coloring ────────────────────────────────────────────────────

def test_fmt_ingest_line_numbered_number_purple():
    """Numbered list number renders in bold purple."""
    out = _fmt_ingest_line("1. Continue with processing")
    assert "#C084FC" in out


def test_fmt_ingest_line_numbered_period_dimmed():
    """Period after numbered list number is dim."""
    out = _fmt_ingest_line("1. Continue with processing")
    assert "[dim]" in out


# ── Run Again button ──────────────────────────────────────────────────────────

async def test_run_again_btn_hidden_initially(tmp_path):
    """Run Again button is hidden when IngestScreen first mounts."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            assert screen.query_one("#run-again-btn", Button).display is False


async def test_run_again_btn_shown_after_turn_complete(tmp_path):
    """Run Again button appears after _on_turn_complete — process may still be alive."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._on_turn_complete()
            await pilot.pause()
            assert screen.query_one("#run-again-btn", Button).display is True


async def test_run_again_btn_shown_after_done(tmp_path):
    """Run Again button becomes visible after _on_done() fires."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._on_done()
            await pilot.pause()
            assert screen.query_one("#run-again-btn", Button).display is True


# ── Title-hyphen coloring ─────────────────────────────────────────────────────

def test_fmt_ingest_line_title_hyphen_colors_label():
    """Text before ' - ' gets bold purple label color."""
    out = _fmt_ingest_line("Issue 1 - Some title text")
    assert "#C084FC" in out
    assert "Issue 1" in out


def test_fmt_ingest_line_title_hyphen_dims_separator():
    """The ' - ' separator is dim."""
    out = _fmt_ingest_line("Issue 1 - Some title text")
    assert "[dim]" in out


def test_fmt_ingest_line_title_hyphen_rest_in_subtitle_color():
    """Text after ' - ' uses the unique subtitle color, not general prose orange."""
    out = _fmt_ingest_line("Issue 1 - Some title text")
    assert "#A8D8EA" in out
    assert "#F4A261" not in out.split("Issue 1")[1]  # subtitle not orange
    assert "Some title text" in out


def test_title_hyphen_re_matches_short_label():
    assert _TITLE_HYPHEN_RE.match("Issue 1 - title") is not None


def test_title_hyphen_re_no_match_long_label():
    """Label longer than 40 chars does not match."""
    long_label = "A" * 45 + " - title"
    assert _TITLE_HYPHEN_RE.match(long_label) is None


def test_fmt_ingest_line_title_hyphen_not_on_tool_lines():
    """Write-tier lines (e.g. 'Wrote x - y.md') are not recolored as titles."""
    out = _fmt_ingest_line("Wrote wiki/sources/log - 001.md")
    assert "[green]" in out
    assert "#C084FC" not in out


def test_title_hyphen_re_no_match_kebab_word():
    """Bare kebab-cased word does not match — no surrounding whitespace."""
    assert _TITLE_HYPHEN_RE.match("kodex-os-layer") is None


def test_title_hyphen_re_no_match_kebab_in_prose():
    """Kebab-cased word inside prose does not trigger title-hyphen split."""
    assert _TITLE_HYPHEN_RE.match("Processing kodex-os-layer entries") is None


def test_fmt_ingest_line_kebab_prose_not_purple():
    """Prose containing kebab-cased identifiers is not colored as a title."""
    out = _fmt_ingest_line("Processing kodex-os-layer entries")
    assert "#C084FC" not in out


def test_fmt_ingest_line_kebab_no_split():
    """Lines with only kebab hyphens (no spaced separator) stay as single color."""
    out = _fmt_ingest_line("Use kos-ingest-v2 to process files")
    assert "#C084FC" not in out


def test_title_hyphen_re_matches_em_dash():
    """Em-dash separator is now matched (Claude uses — not -)."""
    assert _TITLE_HYPHEN_RE.match("Issue 1 — Missing companion") is not None


def test_fmt_ingest_line_em_dash_title_purple():
    """Issue lines with em-dash get purple label color."""
    out = _fmt_ingest_line("Issue 1 — Missing under companion")
    assert "#C084FC" in out


def test_fmt_ingest_line_em_dash_subtitle_color():
    """Subtitle (right of em-dash) uses unique subtitle color, not prose orange."""
    out = _fmt_ingest_line("Issue 1 — Missing under companion")
    assert "#A8D8EA" in out


# ── Markdown heading coloring ─────────────────────────────────────────────────

def test_fmt_ingest_line_h3_with_hyphen_purple_label():
    """### heading with ' - ' gets purple label."""
    out = _fmt_ingest_line("### Issue 3 - Non-standard folder name")
    assert "#C084FC" in out
    assert "Issue 3" in out


def test_fmt_ingest_line_h3_with_hyphen_subtitle_color():
    """### heading with ' - ' gets subtitle color on right side."""
    out = _fmt_ingest_line("### Issue 3 - Non-standard folder name")
    assert "#A8D8EA" in out
    assert "Non-standard folder name" in out


def test_fmt_ingest_line_h3_with_hyphen_no_hashes():
    """### prefix is stripped from output."""
    out = _fmt_ingest_line("### Issue 3 - Non-standard folder name")
    assert "###" not in out


def test_fmt_ingest_line_h2_heading_no_subtitle():
    """## heading without separator gets full bold purple."""
    out = _fmt_ingest_line("## Summary")
    assert "#C084FC" in out
    assert "Summary" in out
    assert "#A8D8EA" not in out


def test_fmt_ingest_line_h1_heading_no_subtitle():
    """# heading without separator gets full bold purple."""
    out = _fmt_ingest_line("# Overview")
    assert "#C084FC" in out
    assert "#A8D8EA" not in out


def test_fmt_ingest_line_h3_em_dash_subtitle():
    """### heading with em-dash separator uses subtitle color."""
    out = _fmt_ingest_line("### Issue 2 — Orphaned scan")
    assert "#C084FC" in out
    assert "#A8D8EA" in out


def test_fmt_ingest_line_title_hyphen_beats_err_re():
    """Structured 'Issue N - Failed …' lines get title-hyphen, not plain red."""
    out = _fmt_ingest_line("Issue 2 - Failed alignment check")
    assert "#C084FC" in out
    assert "[red]" not in out


def test_fmt_ingest_line_title_hyphen_beats_warning_in_body():
    """'Title - Warning about X' gets title-hyphen, not plain red."""
    out = _fmt_ingest_line("Issue 3 - Warning about cross-references")
    assert "#C084FC" in out
    assert "[red]" not in out


def test_fmt_ingest_line_err_re_still_fires_without_hyphen():
    """Lines with error keywords but no ' - ' separator still turn red."""
    out = _fmt_ingest_line("Failed to parse document")
    assert "[red]" in out
    assert "#C084FC" not in out


# ── Numbered question coloring ────────────────────────────────────────────────

def test_fmt_ingest_line_numbered_question_purple_number():
    """'N. Question?' gets purple number AND bright orange question color."""
    out = _fmt_ingest_line("1. Is this the correct volume?")
    assert "#C084FC" in out   # number colored purple
    assert "#FF6B35" in out   # whole line wrapped orange for question


def test_fmt_ingest_line_numbered_question_no_plain_orange():
    """Numbered question does not produce plain light orange (#F4A261)."""
    out = _fmt_ingest_line("2. Should I create a new entry?")
    assert "#FF6B35" in out
    assert out.strip().endswith("[/#FF6B35]")


def test_fmt_ingest_line_non_question_numbered_no_orange_wrap():
    """Non-question numbered line gets purple number but NOT bright orange wrap."""
    out = _fmt_ingest_line("3. Continue with processing")
    assert "#C084FC" in out
    assert "#FF6B35" not in out


# ── _truncate_to_vault() ──────────────────────────────────────────────────────

def test_truncate_to_vault_no_vault_unchanged():
    """Without vault set, path returned as-is."""
    _ingest_mod._vault_root_display = None
    result = _truncate_to_vault("/home/user/vaults/myknowledge/raw/note.pdf")
    assert result == "/home/user/vaults/myknowledge/raw/note.pdf"


def test_truncate_to_vault_strips_prefix(tmp_path):
    """Path under vault_root.parent is truncated to start at vault name."""
    vault = tmp_path / "myknowledge"
    _ingest_mod._vault_root_display = vault
    try:
        full = str(vault / "raw" / "note.pdf")
        result = _truncate_to_vault(full)
        assert result == "myknowledge/raw/note.pdf"
    finally:
        _ingest_mod._vault_root_display = None


def test_truncate_to_vault_unrelated_path_unchanged(tmp_path):
    """Path not under vault parent is returned unchanged."""
    vault = tmp_path / "myknowledge"
    _ingest_mod._vault_root_display = vault
    try:
        result = _truncate_to_vault("/some/other/path/note.pdf")
        assert result == "/some/other/path/note.pdf"
    finally:
        _ingest_mod._vault_root_display = None


# ── _apply_code_highlights() / code span coloring ────────────────────────────

def test_apply_code_highlights_colors_span():
    """Backtick spans get light blue text on dark navy background."""
    out = _apply_code_highlights("Use `kodex-os-layer` here.")
    assert "#9CDCFE" in out
    assert "#1E2832" in out
    assert "kodex-os-layer" in out


def test_apply_code_highlights_strips_backticks():
    """Backtick delimiters are removed from the output."""
    out = _apply_code_highlights("Use `kodex-os-layer` here.")
    assert "`" not in out


def test_apply_code_highlights_no_backtick_unchanged():
    """Plain text with no backticks is returned unchanged."""
    text = "No code spans here."
    assert _apply_code_highlights(text) == text


def test_apply_code_highlights_multiple_spans():
    """Multiple backtick spans in one line are all colored."""
    out = _apply_code_highlights("Run `kos-ingest` then check `wiki/index.md`.")
    assert "kos-ingest" in out
    assert "wiki/index.md" in out
    # Each span produces open+close tags, so 4 occurrences total for 2 spans
    assert out.count("#9CDCFE") == 4


def test_fmt_ingest_line_code_span_in_prose():
    """Code spans within Claude prose get the background highlight."""
    out = _fmt_ingest_line("Processing `kodex-os-layer` vault now.")
    assert "#9CDCFE" in out
    assert "#1E2832" in out


def test_fmt_ingest_line_code_span_in_title_hyphen_body():
    """Code spans in title-hyphen body portion get highlighted."""
    out = _fmt_ingest_line("Issue 1 - Missing `under` companion scan")
    assert "#9CDCFE" in out


def test_fmt_ingest_line_code_span_question():
    """Code spans in questions get highlighted inside the orange wrap."""
    out = _fmt_ingest_line("Should I use `skip` for this entry?")
    assert "#9CDCFE" in out
    assert "#FF6B35" in out


# ── _render_md_table() ───────────────────────────────────────────────────────

_SAMPLE_TABLE = [
    "| Name       | Status  | Count |",
    "|------------|---------|-------|",
    "| FL-vol-001 | OK      | 12    |",
    "| FL-vol-002 | Missing | 0     |",
]


def test_render_md_table_returns_rich_table():
    """Well-formed Markdown table rows produce a Rich Table object."""
    from rich.table import Table
    result = _render_md_table(_SAMPLE_TABLE)
    assert isinstance(result, Table)


def test_render_md_table_column_count():
    """Rich Table has the correct number of columns."""
    result = _render_md_table(_SAMPLE_TABLE)
    assert result is not None
    assert len(result.columns) == 3


def test_render_md_table_too_short_returns_none():
    """A single row with no separator returns None."""
    result = _render_md_table(["| Only | One | Row |"])
    assert result is None


def test_render_md_table_no_separator_returns_none():
    """Rows without a separator row return None."""
    rows = ["| A | B |", "| 1 | 2 |", "| 3 | 4 |"]
    assert _render_md_table(rows) is None


def test_render_md_table_empty_returns_none():
    """Empty list returns None."""
    assert _render_md_table([]) is None


def test_render_md_table_data_row_count():
    """Table has the correct number of data rows."""
    result = _render_md_table(_SAMPLE_TABLE)
    assert result is not None
    assert result.row_count == 2


async def test_log_table_writes_to_richlog(tmp_path):
    """_log_table() writes a Rich Table renderable into the ingest log."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._log_table(_SAMPLE_TABLE)
            await pilot.pause()
            log   = screen.query_one("#ingest-log", RichLog)
            # Table is rendered as a single renderable — log has at least one line
            assert len(log.lines) > 0


async def test_log_table_fallback_on_bad_rows(tmp_path):
    """_log_table() falls back to plain formatted lines when table is malformed."""
    bad_rows = ["| Only | One | Row |"]  # no separator — _render_md_table returns None
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._log_table(bad_rows)
            await pilot.pause()
            log    = screen.query_one("#ingest-log", RichLog)
            written = "\n".join(str(line) for line in log.lines)
            assert "Only" in written


def test_fmt_tool_use_rich_truncates_absolute_path(tmp_path):
    """Tool-use display shows path from vault name, not full absolute prefix."""
    vault = tmp_path / "myknowledge"
    vault.mkdir()
    _ingest_mod._vault_root_display = vault
    try:
        full_path = str(vault / "raw" / "Field-Logs" / "note.pdf")
        out = _fmt_tool_use_rich("Read", {"file_path": full_path})
        assert "myknowledge" in out
        assert str(tmp_path) not in out
        assert "note.pdf" in out
    finally:
        _ingest_mod._vault_root_display = None


# ── Regex group-structure tests (logic, not just color outcome) ───────────────

def test_num_list_re_group_structure():
    """_NUM_LIST_RE captures number, period, and trailing space in separate groups."""
    m = _NUM_LIST_RE.match("3. Some item text")
    assert m is not None
    assert m.group(1) == "3"
    assert m.group(2) == "."
    assert m.group(3) == " "


def test_num_list_re_no_match_mid_sentence():
    """_NUM_LIST_RE is anchored to ^ so 'point 1. text' does not match."""
    assert _NUM_LIST_RE.match("point 1. text") is None


def test_num_list_re_no_match_missing_space():
    """_NUM_LIST_RE requires whitespace after period; '1.text' does not match."""
    assert _NUM_LIST_RE.match("1.text") is None


def test_title_hyphen_re_alt1_groups_hyphen():
    """Hyphen-minus fires alt-1: group(1) is label, group(2) is '-', groups 3-4 absent."""
    m = _TITLE_HYPHEN_RE.match("Issue 5 - description")
    assert m is not None
    assert m.group(1) == "Issue 5"
    assert m.group(2) == "-"
    assert m.group(3) is None   # alt-2 label
    assert m.group(4) is None   # alt-2 separator


def test_title_hyphen_re_alt2_groups_emdash():
    """Em-dash fires alt-2: group(3) is label, group(4) is '—', groups 1-2 absent."""
    m = _TITLE_HYPHEN_RE.match("Issue 5 — description")
    assert m is not None
    assert m.group(1) is None   # alt-1 label
    assert m.group(2) is None   # alt-1 separator
    assert m.group(3) == "Issue 5"
    assert m.group(4) == "—"


def test_title_hyphen_re_alt2_groups_endash():
    """En-dash fires alt-2 the same way as em-dash."""
    m = _TITLE_HYPHEN_RE.match("Step 2 – description")
    assert m is not None
    assert m.group(4) == "–"
    assert m.group(3) == "Step 2"


def test_code_span_re_captures_inner_text():
    """_CODE_SPAN_RE group(1) is the content between the backticks."""
    m = _CODE_SPAN_RE.search("Use `kos-ingest` here.")
    assert m is not None
    assert m.group(1) == "kos-ingest"


def test_code_span_re_no_match_plain_text():
    """_CODE_SPAN_RE does not match text with no backticks."""
    assert _CODE_SPAN_RE.search("no backticks here") is None


def test_warn_md_re_captures_body():
    """_WARN_MD_RE group(1) is the text after **Warning:**."""
    m = _WARN_MD_RE.match("**Warning:** bad frontmatter detected")
    assert m is not None
    assert m.group(1) == "bad frontmatter detected"


def test_warn_md_re_no_match_plain_warning():
    """_WARN_MD_RE does not match plain 'Warning:' without bold markers."""
    assert _WARN_MD_RE.match("Warning: something") is None


def test_md_heading_re_captures_hashes_and_text():
    """_MD_HEADING_RE group(1) is the hash string, group(2) is the heading text."""
    m = _MD_HEADING_RE.match("### Issue 3 - title")
    assert m is not None
    assert m.group(1) == "###"
    assert m.group(2) == "Issue 3 - title"


def test_md_heading_re_h1_and_h2():
    """_MD_HEADING_RE matches # and ## as well as ###."""
    assert _MD_HEADING_RE.match("# Top level") is not None
    assert _MD_HEADING_RE.match("## Second level") is not None


def test_md_heading_re_no_match_non_heading():
    """_MD_HEADING_RE does not match lines that do not start with #."""
    assert _MD_HEADING_RE.match("normal prose line") is None
    assert _MD_HEADING_RE.match("Issue 1 - no hash") is None


def test_render_md_table_sep_row_excluded_from_data():
    """The separator row (|---|---| line) must not appear in data rows."""
    result = _render_md_table(_SAMPLE_TABLE)
    assert result is not None
    # 2 data rows only (separator row excluded)
    assert result.row_count == 2


def test_fmt_ingest_line_write_priority_over_title_hyphen():
    """Write-tier lines starting 'Wrote X - Y.md' stay green, not title-hyphen purple."""
    out = _fmt_ingest_line("Wrote wiki/sources/log - 001.md")
    assert "[green]" in out
    assert "#C084FC" not in out


def test_fmt_ingest_line_read_priority_over_title_hyphen():
    """Read-tier lines are not recolored as title-hyphen even if they contain ' - '."""
    out = _fmt_ingest_line("Reading raw/Field-Logs - some path")
    assert "[dim cyan]" in out
    assert "#C084FC" not in out


# ── _send_user_input() logic ──────────────────────────────────────────────────

async def test_send_user_input_formats_plain_message(tmp_path):
    """Without pending_tool_id the message is a plain user text content block."""
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdin.write = MagicMock()

    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._proc = mock_proc
            screen._pending_tool_id = None
            screen.query_one("#user-input", Input).value = "skip"
            screen._send_user_input()
            await pilot.pause()

    written = mock_proc.stdin.write.call_args[0][0]
    payload = json.loads(written)
    content = payload["message"]["content"]
    assert len(content) == 1
    assert content[0]["type"] == "text"
    assert content[0]["text"] == "skip"


async def test_send_user_input_formats_tool_result_when_pending(tmp_path):
    """With pending_tool_id the message wraps in a tool_result content block."""
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdin.write = MagicMock()

    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._proc = mock_proc
            screen._pending_tool_id = "tool-abc-123"
            screen.query_one("#user-input", Input).value = "1"
            screen._send_user_input()
            await pilot.pause()

    written = mock_proc.stdin.write.call_args[0][0]
    payload = json.loads(written)
    content = payload["message"]["content"]
    assert len(content) == 1
    assert content[0]["type"] == "tool_result"
    assert content[0]["tool_use_id"] == "tool-abc-123"
    assert content[0]["content"][0]["text"] == "1"


async def test_send_user_input_clears_pending_tool_id(tmp_path):
    """Sending a tool_result clears _pending_tool_id so the next message is plain."""
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()

    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._proc = mock_proc
            screen._pending_tool_id = "tool-abc-123"
            screen.query_one("#user-input", Input).value = "1"
            screen._send_user_input()
            await pilot.pause()
            assert screen._pending_tool_id is None


# ── _show_question() logic ────────────────────────────────────────────────────

async def test_show_question_writes_options_to_log(tmp_path):
    """_show_question() writes the question and each option to the ingest log."""
    options = [
        {"label": "Skip", "description": "ignore this file"},
        {"label": "Ingest", "description": "process now"},
    ]
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._show_question("What should I do?", options, "tool-xyz")
            await pilot.pause()
            log    = screen.query_one("#ingest-log", RichLog)
            written = "\n".join(str(line) for line in log.lines)
            assert "What should I do?" in written
            assert "Skip" in written
            assert "Ingest" in written


async def test_show_question_sets_pending_tool_id(tmp_path):
    """_show_question() stores the tool_id so _send_user_input knows to wrap it."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._show_question("Choose:", [{"label": "A"}], "tool-99")
            await pilot.pause()
            assert screen._pending_tool_id == "tool-99"


async def test_show_question_changes_input_placeholder(tmp_path):
    """_show_question() updates the input placeholder to prompt for a selection."""
    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._show_question("Choose:", [{"label": "A"}], "tool-1")
            await pilot.pause()
            placeholder = screen.query_one("#user-input", Input).placeholder
            assert "option" in placeholder.lower() or "number" in placeholder.lower()


# ── on_unmount() process cleanup ──────────────────────────────────────────────

async def test_on_unmount_terminates_running_process(tmp_path):
    """on_unmount() terminates a live subprocess so it does not become a zombie."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None    # process still running
    mock_proc.stdin = MagicMock()

    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._proc = mock_proc
            # Trigger unmount by popping the screen
            await pilot.app.pop_screen()
            await pilot.pause()

    mock_proc.terminate.assert_called_once()


async def test_on_unmount_closes_stdin(tmp_path):
    """on_unmount() closes stdin before terminating the process."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.stdin = MagicMock()

    with patch("app.config.exists", return_value=False), \
         patch("screens.ingest.shutil.which", return_value=None):
        async with KosCaptureApp().run_test() as pilot:
            await pilot.pause()
            screen = IngestScreen(tmp_path)
            await pilot.app.push_screen(screen)
            await pilot.pause()
            screen._proc = mock_proc
            await pilot.app.pop_screen()
            await pilot.pause()

    mock_proc.stdin.close.assert_called_once()
