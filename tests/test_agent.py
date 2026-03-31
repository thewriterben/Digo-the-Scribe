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


# ---------------------------------------------------------------------------
# DigoAgent — live listening integration
# ---------------------------------------------------------------------------


class TestDigoAgentListen:
    def test_create_listener_returns_audio_listener(self):
        agent = _make_agent_no_llm()
        from digo.audio_listener import AudioListener

        listener = agent.create_listener()
        assert isinstance(listener, AudioListener)

    def test_create_listener_custom_params(self):
        agent = _make_agent_no_llm()
        listener = agent.create_listener(
            energy_threshold=500,
            pause_threshold=2.0,
            phrase_time_limit=15.0,
        )
        assert listener._recogniser.energy_threshold == 500

    def test_take_notes_from_empty_session(self):
        from digo.audio_listener import ListenSession

        agent = _make_agent_no_llm()
        session = ListenSession(meeting_title="Empty Meeting", meeting_date="2026-03-28")
        result = agent.take_notes_from_session(session)
        assert "No speech" in result

    def test_take_notes_from_session_with_segments(self):
        from digo.audio_listener import ListenSegment, ListenSession

        agent = _make_agent_with_mock_llm("## Notes from listened meeting")
        session = ListenSession(meeting_title="Strategy Call", meeting_date="2026-03-28")
        session.add_segment(ListenSegment(text="Let's discuss the plan.", timestamp="14:00:00"))
        session.add_segment(ListenSegment(text="Agreed.", timestamp="14:00:05"))

        notes = agent.take_notes_from_session(session)
        assert "Notes" in notes
        agent._llm.messages.create.assert_called_once()


# ---------------------------------------------------------------------------
# DigoAgent — Google Meet integration
# ---------------------------------------------------------------------------


class TestDigoAgentMeetIntegration:
    def test_create_meet_client(self):
        from digo.google_meet import GoogleMeetClient

        agent = _make_agent_no_llm()
        client = agent.create_meet_client()
        assert isinstance(client, GoogleMeetClient)

    def test_get_next_meet_session_returns_session(self):
        from digo.google_meet import MeetSession

        agent = _make_agent_no_llm()
        mock_session = MeetSession(
            title="Test Meet",
            meeting_date="2026-03-28",
            start_time="2026-03-28T14:00:00Z",
            end_time="2026-03-28T15:00:00Z",
            meet_link="https://meet.google.com/abc-defg-hij",
            calendar_event_id="event123",
        )
        mock_client = MagicMock()
        mock_client.get_next_meeting.return_value = mock_session

        with patch.object(agent, "create_meet_client", return_value=mock_client):
            result = agent.get_next_meet_session()
        assert result is not None
        assert result.title == "Test Meet"

    def test_get_next_meet_session_returns_none_on_error(self):
        agent = _make_agent_no_llm()
        mock_client = MagicMock()
        mock_client.get_next_meeting.side_effect = Exception("API error")

        with patch.object(agent, "create_meet_client", return_value=mock_client):
            result = agent.get_next_meet_session()
        assert result is None

    def test_get_meet_session_by_event_id(self):
        from digo.google_meet import MeetSession

        agent = _make_agent_no_llm()
        mock_session = MeetSession(
            title="Specific Meet",
            meeting_date="2026-03-28",
            start_time="2026-03-28T14:00:00Z",
            end_time="2026-03-28T15:00:00Z",
            meet_link="https://meet.google.com/xyz-abcd-efg",
            calendar_event_id="specific-event",
        )
        mock_client = MagicMock()
        mock_client.get_meeting_by_event_id.return_value = mock_session

        with patch.object(agent, "create_meet_client", return_value=mock_client):
            result = agent.get_meet_session_by_event_id("specific-event")
        assert result is not None
        assert result.title == "Specific Meet"

    def test_get_meet_session_by_event_id_returns_none_on_error(self):
        agent = _make_agent_no_llm()
        mock_client = MagicMock()
        mock_client.get_meeting_by_event_id.side_effect = Exception("Not found")

        with patch.object(agent, "create_meet_client", return_value=mock_client):
            result = agent.get_meet_session_by_event_id("bad-id")
        assert result is None


# ---------------------------------------------------------------------------
# DigoAgent — progress reports
# ---------------------------------------------------------------------------


class TestDigoAgentProgressReport:
    def test_generate_progress_report_calls_llm(self):
        agent = _make_agent_with_mock_llm("## Progress Report\n\nAll on track.")
        report = agent.generate_progress_report("## Meeting Notes\n\nDiscussed milestones.")
        assert "Progress Report" in report
        agent._llm.messages.create.assert_called_once()

    def test_generate_progress_report_raises_without_llm(self):
        agent = _make_agent_no_llm()
        with pytest.raises(RuntimeError, match="LLM client not initialised"):
            agent.generate_progress_report("## Meeting Notes")


# ---------------------------------------------------------------------------
# DigoAgent — CFV integration
# ---------------------------------------------------------------------------


class TestDigoAgentCFV:
    def test_generate_cfv_report(self, tmp_path: Path):
        from digo import config as cfg

        original = cfg.REPORTS_DIR
        cfg.REPORTS_DIR = tmp_path / "reports"

        try:
            agent = _make_agent_no_llm()
            mock_client = MagicMock()
            from digo.cfv_client import CFVCoinMetrics, CFVPortfolioSnapshot

            snapshot = CFVPortfolioSnapshot(
                coins=[
                    CFVCoinMetrics(
                        symbol="BTC",
                        name="Bitcoin",
                        current_price=50000.0,
                        fair_value=55000.0,
                        cfv_score=0.9,
                        valuation_status="UNDERVALUED",
                        price_multiplier=1.1,
                        confidence_level=0.85,
                    ),
                ],
                fetched_at="2026-03-28T00:00:00Z",
            )
            mock_client.fetch_all_coins.return_value = snapshot
            agent._cfv_client = mock_client

            report = agent.generate_cfv_report(snapshot=snapshot)
            assert isinstance(report, str)
            assert "CFV" in report or "Bitcoin" in report or "LLM" in report
        finally:
            cfg.REPORTS_DIR = original

    def test_check_cfv_alerts(self):
        agent = _make_agent_no_llm()
        from digo.cfv_client import CFVPortfolioSnapshot

        snapshot = CFVPortfolioSnapshot()
        alerts, report = agent.check_cfv_alerts(snapshot=snapshot)
        assert isinstance(alerts, list)
        assert isinstance(report, str)
