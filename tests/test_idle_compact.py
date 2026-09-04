"""Unit tests for the pure helpers.

The screen fixtures are verbatim captures from real sessions on a live
machine — including the quirks that broke earlier versions of the parser: a
tab title embedded in the box's top rule, a non-breaking space after the
prompt marker, and reply content that draws its own boxes and quotes.
"""
import json
from pathlib import Path

import pytest

MANIFEST = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"

RULE = "─" * 152

IDLE = f"""\
● Done.

{RULE}
❯ 
{RULE}
  ⏵⏵ auto mode on (shift+tab to cycle) · ← for agents
"""

TITLED_RULE_IDLE = """\
✻ Worked for 7s · done 5:42 PM

──────────────────────────────────────────────── cb-st-terms-10-r1 ─
❯ 
────────────────────────────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents
"""

DRAFT = f"""\
● Sure.

{RULE}
❯ whats PE ration
{RULE}
  ⏵⏵ auto mode on (shift+tab to cycle)
"""

BUSY = f"""\
● Working on it

{RULE}
❯ 
{RULE}
  ⏵⏵ auto mode on · esc to interrupt
"""

# A dialog is open: one rule, no input box, and box-drawn content above it.
DIALOG = f"""\
                    │ │ ▸ 860 devices in │                       │  │
                    │ │   >1 source      │   Never blank.        │  │
                    │ └──────────────────┴───────────────────────┘  │
                    └───────────────────────────────────────────────┘
{RULE}
  Chat about this

Enter to select · ↑/↓ to navigate · Esc to cancel
"""

# Tab scrolled up: the box is off-screen, but an old prompt echo is not.
SCROLLED = """\
❯ what is a cap rate

  Cap rate uses NOI — before debt service, before taxes.
  P/E uses net income — after interest, after taxes.

  So they're not directly comparable.
"""


class TestReadPromptBox:
    def test_empty_box_is_ready(self, ic):
        assert ic.read_prompt_box(IDLE) == ("", False)

    def test_tab_title_in_the_top_rule(self, ic):
        """The top rule carries the tab name; it is still a rule."""
        assert ic.read_prompt_box(TITLED_RULE_IDLE) == ("", False)

    def test_unsent_draft_is_reported(self, ic):
        text, busy = ic.read_prompt_box(DRAFT)
        assert text == "whats PE ration" and not busy

    def test_busy_session_flagged(self, ic):
        text, busy = ic.read_prompt_box(BUSY)
        assert text == "" and busy

    def test_open_dialog_has_no_box(self, ic):
        """Content-drawn boxes must not be mistaken for the input box."""
        text, busy = ic.read_prompt_box(DIALOG)
        assert text is None
        assert busy  # "Esc to cancel"

    def test_scrolled_away_has_no_box(self, ic):
        """An old prompt echo in the scrollback is not the live input box."""
        assert ic.read_prompt_box(SCROLLED) == (None, False)

    def test_no_box_is_distinct_from_empty_box(self, ic):
        """The caller refuses on None but proceeds on "" — never conflate."""
        assert ic.read_prompt_box(SCROLLED)[0] is None
        assert ic.read_prompt_box(IDLE)[0] == ""


class TestIsRule:
    def test_plain_rule(self, ic):
        assert ic.is_rule(RULE)

    def test_titled_rule(self, ic):
        assert ic.is_rule("──────────────────────── my-session ─")

    def test_table_border_is_not_a_rule(self, ic):
        assert not ic.is_rule("│ └──────────────────┴──────────────┘  │")
        assert not ic.is_rule("└────────────────────────────────────┘")

    def test_short_line_is_not_a_rule(self, ic):
        assert not ic.is_rule("─────")

    def test_prose_is_not_a_rule(self, ic):
        assert not ic.is_rule("  - Cap rate uses NOI — before debt service")


class TestMapTerminalId:
    def test_maps_by_creation_order(self, ic):
        paths = ["/Sessions/3", "/Sessions/40", "/Sessions/56"]
        assert ic.map_terminal_id(paths, [7, 88, 109], "/Sessions/56") == 109
        assert ic.map_terminal_id(paths, [7, 88, 109], "/Sessions/3") == 7

    def test_sorts_numerically_not_lexically(self, ic):
        paths = ["/Sessions/9", "/Sessions/10"]
        assert ic.map_terminal_id(paths, [1, 2], "/Sessions/10") == 2

    def test_refuses_on_count_mismatch(self, ic):
        assert ic.map_terminal_id(["/Sessions/1"], [1, 2], "/Sessions/1") is None

    def test_refuses_unknown_path(self, ic):
        assert ic.map_terminal_id(["/Sessions/1"], [1], "/Sessions/9") is None


class TestContextTokens:
    def test_sums_the_cache_tiers(self, ic):
        usage = {"input_tokens": 2, "cache_read_input_tokens": 111097,
                 "cache_creation_input_tokens": 2936, "output_tokens": 3931}
        assert ic.context_tokens(usage) == 114035

    def test_output_tokens_are_not_context(self, ic):
        assert ic.context_tokens({"input_tokens": 10, "output_tokens": 900}) == 10

    def test_missing_usage(self, ic):
        assert ic.context_tokens(None) == 0


class TestParseTs:
    def test_registry_millis(self, ic):
        assert ic.parse_ts(1788483708335) == pytest.approx(1788483708.335)

    def test_transcript_iso(self, ic):
        assert ic.parse_ts("2026-09-04T01:06:10.343Z") == pytest.approx(
            1788483970.343, abs=1)

    def test_missing(self, ic):
        assert ic.parse_ts(None) == 0.0


class TestHumanize:
    @pytest.mark.parametrize("seconds,expected", [
        (5, "5s"), (600, "10m"), (2700, "45m"), (7200, "2h00m"), (259200, "3d"),
    ])
    def test_formats(self, ic, seconds, expected):
        assert ic.humanize(seconds) == expected


class TestManifest:
    def test_is_valid_json_with_required_fields(self):
        data = json.loads(MANIFEST.read_text())
        assert data["name"] == "idle-compact"
        assert data["version"] and data["description"]

    def test_skill_frontmatter_present(self):
        skill = MANIFEST.parent.parent / "skills" / "idle-compact" / "SKILL.md"
        text = skill.read_text()
        assert text.startswith("---\nname: idle-compact\n")
        assert "description:" in text.split("---")[1]


class TestEnterDelivery:
    """Regression guards for how a terminal backend delivers Enter.

    Both of these were found only by driving a real session: text and its
    terminator arriving in one write are read by the TUI as a *paste*, so the
    newline lands inside the prompt box and the text sits there unsent. A
    terminator arriving on its own is a real Enter. An empty string delivers
    nothing at all.
    """

    def test_enter_is_a_carriage_return(self, ic):
        assert ic.ENTER == "\r"

    def test_yakuake_sends_text_then_a_separate_enter(self, ic, monkeypatch):
        calls = []
        monkeypatch.setattr(ic, "dbus", lambda *a: calls.append(a) or "")
        monkeypatch.setattr(ic.time, "sleep", lambda _: None)
        backend = ic.YakuakeBackend("/Sessions/56")
        backend.tid = 109
        backend.send_line("/compact")

        assert len(calls) == 2, "text and Enter must be separate writes"
        assert calls[0][-1] == "/compact"
        assert calls[1][-1] == ic.ENTER
        assert calls[1][-1] != "", "an empty string delivers no keystroke"

    def test_konsole_sends_text_then_a_separate_enter(self, ic, monkeypatch):
        calls = []
        monkeypatch.setattr(ic, "dbus", lambda *a: calls.append(a) or "")
        monkeypatch.setattr(ic.time, "sleep", lambda _: None)
        ic.KonsoleBackend(":1.75", "/Sessions/56").send_line("/compact")
        assert [c[-1] for c in calls] == ["/compact", ic.ENTER]


class TestRefusalDetection:
    def test_probe_output_is_not_a_refusal(self, ic):
        """The probe deliberately produces "Unknown command" moments before
        /compact is sent; matching it would misreport why compaction failed."""
        assert not any("unknown command" in r for r in ic.REFUSALS)

    def test_real_refusals_are_matched(self, ic):
        content = "<local-command-stdout>Not enough messages to compact.</local-command-stdout>"
        assert any(r in content.lower() for r in ic.REFUSALS)
