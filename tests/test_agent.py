"""Tests for the core DigoAgent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from digo import config
from digo.agent import DigoAgent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_no_llm() -> DigoAgent:
    """Return a DigoAgent with no LLM key (offline mode)."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
        return DigoAgent()


def _make_agent_with_mock_llm(response_text: str = "Mock LLM response") -> DigoAgent:
    """Return a DigoAgent whose LLM always returns *response_text*."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test-fake"}):
        agent = DigoAgent()

    # Patch the internal Anthropic client
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.text = response_text
    mock_response.content = [mock_block]
    agent._llm = MagicMock()
    agent._llm.messages.create.return_value = mock_response
    return agent


# ---------------------------------------------------------------------------
# DigoAgent — initialisation
# ---------------------------------------------------------------------------


class TestDigoAgentInit:
    def test_no_api_key_llm_is_none(self):
        agent = _make_agent_no_llm()
        assert agent._llm is None

    def test_status_returns_string(self):
        agent = _make_agent_no_llm()
        s = agent.status()
        assert isinstance(s, str)
        assert "Digo the Scribe" in s

    def test_status_warns_missing_key(self):
        agent = _make_agent_no_llm()
        s = agent.status()
        assert "ANTHROPIC_API_KEY" in s


# ---------------------------------------------------------------------------
# DigoAgent — resource loading
# ---------------------------------------------------------------------------


class TestDigoAgentLoadResources:
    def test_missing_pdfs_return_warnings(self):
        agent = _make_agent_no_llm()
        # Ensure PDFs are "missing" regardless of local environment
        with (
            patch.object(config, "BATTLE_PLAN_PDF", Path("/nonexistent/battle_plan.pdf")),
            patch.object(config, "BEYOND_BITCOIN_PDF", Path("/nonexistent/beyond_bitcoin.pdf")),
            patch.object(
                config,
                "DIGITAL_GOLD_WHITE_PAPER_PDF",
                Path("/nonexistent/digital_gold_white_paper.pdf"),
            ),
        ):
            warnings = agent.load_resources()
        # All three PDFs are absent in the test environment
        assert any("Battle Plan" in w for w in warnings)
        assert any("Beyond Bitcoin" in w for w in warnings)
        assert any("Digital Gold White Paper" in w for w in warnings)

    def test_load_resource_from_path(self, tmp_path: Path):
        agent = _make_agent_no_llm()
        pdf_path = tmp_path / "extra.pdf"
        pdf_path.write_bytes(b"%PDF fake")

        mock_pdf = MagicMock()
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Extra document text."
        mock_pdf.pages = [mock_page]

        with patch("digo.pdf_processor.pdfplumber.open", return_value=mock_pdf):
            agent.load_resource_from_path("Extra Doc", pdf_path)

        assert "Extra Doc" in agent._library.loaded_names()


# ---------------------------------------------------------------------------
# DigoAgent — note-taking
# ---------------------------------------------------------------------------


class TestDigoAgentNoteTaking:
    def test_take_notes_from_text_calls_llm(self):
        agent = _make_agent_with_mock_llm("## Notes\n\nSome notes here.")
        raw = "Alice: Let's discuss the Battle Plan.\nBob: Agreed."
        notes = agent.take_notes_from_text(raw, meeting_title="Test Meeting")
        assert "Notes" in notes
        agent._llm.messages.create.assert_called_once()

    def test_take_notes_from_file(self, tmp_path: Path):
        f = tmp_path / "transcript.txt"
        f.write_text("Alice: Hello.\nBob: Hi.\n", encoding="utf-8")
        agent = _make_agent_with_mock_llm("## Meeting Notes")
        notes = agent.take_notes_from_file(f, meeting_title="File Test")
        assert isinstance(notes, str)

    def test_take_notes_raises_without_llm(self):
        agent = _make_agent_no_llm()
        with pytest.raises(RuntimeError, match="LLM client not initialised"):
            agent.take_notes_from_text("Alice: Hello.", meeting_title="Test")


# ---------------------------------------------------------------------------
# DigoAgent — escalation
# ---------------------------------------------------------------------------


class TestDigoAgentEscalation:
    def test_escalation_notice_contains_required_fields(self):
        agent = _make_agent_no_llm()
        notice = agent.create_escalation_notice(
            topic="CFV Fund valuation",
            context="Discussed during the opening of the meeting.",
            reason="Not found in Battle Plan pages reviewed.",
            meeting_title="Q1 Review",
            meeting_date="2026-03-26",
        )
        assert "CFV Fund valuation" in notice
        assert "Benjamin J. Snider" in notice
        assert "Q1 Review" in notice
        assert "2026-03-26" in notice
        assert "NEEDS VERIFICATION" in notice

    def test_escalation_without_date_uses_today(self):
        import datetime

        agent = _make_agent_no_llm()
        notice = agent.create_escalation_notice(
            topic="Topic",
            context="Context",
            reason="Reason",
            meeting_title="Meeting",
        )
        today = datetime.date.today().isoformat()
        assert today in notice


# ---------------------------------------------------------------------------
# DigoAgent — persistence
# ---------------------------------------------------------------------------


class TestDigoAgentPersistence:
    def test_save_notes_creates_file(self, tmp_path: Path):
        agent = _make_agent_no_llm()
        # Override output path for testing
        from digo import config as cfg

        original = cfg.NOTES_DIR
        cfg.NOTES_DIR = tmp_path / "notes"

        try:
            path = agent.save_notes("## Notes\n\nContent.", "test_meeting")
            assert path.exists()
            assert path.read_text() == "## Notes\n\nContent."
        finally:
            cfg.NOTES_DIR = original

    def test_save_report_creates_file(self, tmp_path: Path):
        agent = _make_agent_no_llm()
        from digo import config as cfg

        original = cfg.REPORTS_DIR
        cfg.REPORTS_DIR = tmp_path / "reports"

        try:
            path = agent.save_report("## Report\n\nContent.", "test_slug")
            assert path.exists()
            assert "_report.md" in path.name
        finally:
            cfg.REPORTS_DIR = original
