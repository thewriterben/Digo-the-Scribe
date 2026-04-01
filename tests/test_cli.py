"""Tests for the CLI interface."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from digo.cli import (
    build_parser,
    cmd_cfv_alerts,
    cmd_cfv_analysis,
    cmd_cfv_report,
    cmd_cfv_snapshot,
    cmd_escalate,
    cmd_listen,
    cmd_load_resource,
    cmd_notes,
    cmd_report,
    cmd_status,
)

# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_parser_returns_argumentparser(self):
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_version_flag(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_status_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_notes_subcommand_with_transcript(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "notes",
                "--transcript",
                "meeting.txt",
                "--title",
                "Q1 Review",
                "--date",
                "2026-03-26",
            ]
        )
        assert args.command == "notes"
        assert args.transcript == "meeting.txt"
        assert args.title == "Q1 Review"
        assert args.date == "2026-03-26"

    def test_notes_subcommand_with_text(self):
        parser = build_parser()
        args = parser.parse_args(["notes", "--text", "Alice: Hello."])
        assert args.command == "notes"
        assert args.text == "Alice: Hello."

    def test_report_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["report", "--notes", "output/notes/test.md"])
        assert args.command == "report"
        assert args.notes == "output/notes/test.md"

    def test_escalate_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "escalate",
                "--topic",
                "CFV valuation",
                "--context",
                "Discussed in meeting",
                "--reason",
                "Not in Battle Plan",
            ]
        )
        assert args.command == "escalate"
        assert args.topic == "CFV valuation"

    def test_verbose_flag(self):
        parser = build_parser()
        args = parser.parse_args(["-v", "status"])
        assert args.verbose is True

    def test_no_subcommand_raises(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_load_resource_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["load-resource", "--name", "CFV Metrics", "--path", "cfv.pdf"])
        assert args.command == "load-resource"
        assert args.name == "CFV Metrics"
        assert args.path == "cfv.pdf"


# ---------------------------------------------------------------------------
# Command functions
# ---------------------------------------------------------------------------


class TestCmdStatus:
    def test_status_prints_output(self, capsys):
        agent = MagicMock()
        agent.status.return_value = "=== Digo the Scribe — Status ==="
        args = argparse.Namespace()
        cmd_status(agent, args)
        agent.status.assert_called_once()


class TestCmdNotes:
    def test_notes_from_transcript(self, tmp_path: Path):
        f = tmp_path / "transcript.txt"
        f.write_text("Alice: Hello.\nBob: Hi.\n", encoding="utf-8")

        agent = MagicMock()
        agent.take_notes_from_file.return_value = "## Meeting Notes"
        agent.save_notes.return_value = tmp_path / "notes.md"

        args = argparse.Namespace(
            transcript=str(f),
            text=None,
            title="Test Meeting",
            date="2026-03-26",
        )
        cmd_notes(agent, args)
        agent.take_notes_from_file.assert_called_once()
        agent.save_notes.assert_called_once()

    def test_notes_from_text(self, tmp_path: Path):
        agent = MagicMock()
        agent.take_notes_from_text.return_value = "## Meeting Notes"
        agent.save_notes.return_value = tmp_path / "notes.md"

        args = argparse.Namespace(
            transcript=None,
            text="Alice: Hello.",
            title="Quick Sync",
            date=None,
        )
        cmd_notes(agent, args)
        agent.take_notes_from_text.assert_called_once()

    def test_notes_no_input_exits(self):
        agent = MagicMock()
        args = argparse.Namespace(transcript=None, text=None, title=None, date=None)
        with pytest.raises(SystemExit):
            cmd_notes(agent, args)


class TestCmdReport:
    def test_report_reads_notes_file(self, tmp_path: Path):
        notes_file = tmp_path / "notes.md"
        notes_file.write_text("## Notes\n\nContent.", encoding="utf-8")

        agent = MagicMock()
        agent.generate_progress_report.return_value = "## Report"
        agent.save_report.return_value = tmp_path / "report.md"

        args = argparse.Namespace(notes=str(notes_file))
        cmd_report(agent, args)
        agent.generate_progress_report.assert_called_once()
        agent.save_report.assert_called_once()

    def test_report_missing_file_exits(self):
        agent = MagicMock()
        args = argparse.Namespace(notes="/nonexistent/file.md")
        with pytest.raises(SystemExit):
            cmd_report(agent, args)


class TestCmdEscalate:
    def test_escalate_creates_notice(self):
        agent = MagicMock()
        agent.create_escalation_notice.return_value = "Subject: [Digo — NEEDS VERIFICATION]"

        args = argparse.Namespace(
            topic="CFV valuation",
            context="Discussed in meeting",
            reason="Not found in Battle Plan",
            title="Q1 Review",
            date="2026-03-26",
        )
        cmd_escalate(agent, args)
        agent.create_escalation_notice.assert_called_once()

    def test_escalate_defaults(self):
        agent = MagicMock()
        agent.create_escalation_notice.return_value = "Notice"

        args = argparse.Namespace(
            topic="Topic",
            context=None,
            reason=None,
            title=None,
            date=None,
        )
        cmd_escalate(agent, args)
        call_kwargs = agent.create_escalation_notice.call_args
        # Defaults should be applied
        assert call_kwargs[1]["context"] == ""
        assert "Could not confirm" in call_kwargs[1]["reason"]
        assert call_kwargs[1]["meeting_title"] == "Unknown Meeting"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


class TestMain:
    @patch("digo.cli.DigoAgent")
    def test_main_status(self, mock_agent_cls):
        agent_instance = MagicMock()
        agent_instance.load_resources.return_value = []
        agent_instance.status.return_value = "OK"
        mock_agent_cls.return_value = agent_instance

        from digo.cli import main

        with patch("sys.argv", ["digo", "status"]):
            main()
        agent_instance.status.assert_called_once()

    @patch("digo.cli.DigoAgent")
    def test_main_shows_warnings(self, mock_agent_cls, capsys):
        agent_instance = MagicMock()
        agent_instance.load_resources.return_value = ["Warning: missing PDF"]
        agent_instance.status.return_value = "OK"
        mock_agent_cls.return_value = agent_instance

        from digo.cli import main

        with patch("sys.argv", ["digo", "status"]):
            main()


# ---------------------------------------------------------------------------
# load-resource command
# ---------------------------------------------------------------------------


class TestCmdLoadResource:
    def test_load_resource_success(self, tmp_path: Path):
        pdf_file = tmp_path / "extra.pdf"
        pdf_file.write_bytes(b"%PDF fake content")

        agent = MagicMock()
        args = argparse.Namespace(name="Extra Doc", path=str(pdf_file))
        cmd_load_resource(agent, args)
        agent.load_resource_from_path.assert_called_once_with("Extra Doc", pdf_file)

    def test_load_resource_file_not_found(self):
        agent = MagicMock()
        args = argparse.Namespace(name="Missing", path="/nonexistent/file.pdf")
        with pytest.raises(SystemExit):
            cmd_load_resource(agent, args)

    def test_load_resource_not_pdf(self, tmp_path: Path):
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("not a pdf", encoding="utf-8")

        agent = MagicMock()
        args = argparse.Namespace(name="Bad File", path=str(txt_file))
        with pytest.raises(SystemExit):
            cmd_load_resource(agent, args)

    def test_load_resource_agent_error(self, tmp_path: Path):
        pdf_file = tmp_path / "bad.pdf"
        pdf_file.write_bytes(b"%PDF corrupted")

        agent = MagicMock()
        agent.load_resource_from_path.side_effect = RuntimeError("PDF parse error")
        args = argparse.Namespace(name="Bad PDF", path=str(pdf_file))
        with pytest.raises(SystemExit):
            cmd_load_resource(agent, args)


# ---------------------------------------------------------------------------
# listen command — parser
# ---------------------------------------------------------------------------


class TestBuildParserListen:
    def test_listen_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["listen", "--title", "Weekly Sync", "--date", "2026-03-28"])
        assert args.command == "listen"
        assert args.title == "Weekly Sync"
        assert args.date == "2026-03-28"

    def test_listen_subcommand_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["listen"])
        assert args.command == "listen"
        assert args.title is None
        assert args.date is None

    def test_listen_meet_flag(self):
        parser = build_parser()
        args = parser.parse_args(["listen", "--meet"])
        assert args.meet is True

    def test_listen_event_id_flag(self):
        parser = build_parser()
        args = parser.parse_args(["listen", "--event-id", "abc123"])
        assert args.event_id == "abc123"

    def test_listen_meet_with_title_override(self):
        parser = build_parser()
        args = parser.parse_args(
            ["listen", "--meet", "--title", "Custom Title", "--date", "2026-04-01"]
        )
        assert args.meet is True
        assert args.title == "Custom Title"
        assert args.date == "2026-04-01"


# ---------------------------------------------------------------------------
# listen command — execution
# ---------------------------------------------------------------------------


class TestCmdListen:
    def test_listen_import_error_exits(self):
        agent = MagicMock()
        agent.create_listener.side_effect = ImportError("SpeechRecognition not installed")
        args = argparse.Namespace(title="Test", date=None, meet=False, event_id=None)
        with pytest.raises(SystemExit):
            cmd_listen(agent, args)

    def test_listen_no_segments_captured(self, tmp_path: Path):
        """When no speech is captured, no notes are generated."""
        from digo.audio_listener import ListenSession

        agent = MagicMock()
        mock_listener = MagicMock()
        agent.create_listener.return_value = mock_listener

        session = ListenSession(meeting_title="Test", meeting_date="2026-03-28")

        # Simulate: is_listening returns False immediately (listener stops right away)
        mock_listener.is_listening = False
        mock_listener.stop.return_value = session
        mock_listener.get_transcript.return_value = session

        args = argparse.Namespace(title="Test", date="2026-03-28", meet=False, event_id=None)
        cmd_listen(agent, args)

        # No notes should be generated since no segments
        agent.take_notes_from_session.assert_not_called()

    def test_listen_with_segments_generates_notes(self, tmp_path: Path):
        """When speech segments are captured, notes are generated and saved."""
        from digo.audio_listener import ListenSegment, ListenSession

        agent = MagicMock()
        mock_listener = MagicMock()
        agent.create_listener.return_value = mock_listener

        session = ListenSession(meeting_title="Strategy Call", meeting_date="2026-03-28")
        session.add_segment(ListenSegment(text="Let's discuss the plan.", timestamp="14:00:00"))
        session.add_segment(ListenSegment(text="Agreed, let's go.", timestamp="14:00:05"))

        mock_listener.is_listening = False
        mock_listener.stop.return_value = session
        mock_listener.get_transcript.return_value = session

        agent.take_notes_from_session.return_value = "## Meeting Notes"
        agent.save_notes.return_value = tmp_path / "notes.md"

        args = argparse.Namespace(
            title="Strategy Call", date="2026-03-28", meet=False, event_id=None
        )
        cmd_listen(agent, args)

        agent.take_notes_from_session.assert_called_once_with(session)
        agent.save_notes.assert_called_once()

    def test_listen_with_meet_flag_uses_session_metadata(self, tmp_path: Path):
        """When --meet is used and a session is found, metadata is used."""
        from digo.audio_listener import ListenSession
        from digo.google_meet import MeetSession

        agent = MagicMock()
        mock_listener = MagicMock()
        agent.create_listener.return_value = mock_listener

        meet_session = MeetSession(
            title="Q1 Strategy Review",
            meeting_date="2026-03-28",
            start_time="2026-03-28T14:00:00Z",
            end_time="2026-03-28T15:00:00Z",
            meet_link="https://meet.google.com/abc-defg-hij",
            calendar_event_id="event123",
            participants=["Alice", "Bob"],
        )
        agent.get_next_meet_session.return_value = meet_session

        listen_session = ListenSession(
            meeting_title="Q1 Strategy Review", meeting_date="2026-03-28"
        )
        mock_listener.is_listening = False
        mock_listener.stop.return_value = listen_session
        mock_listener.get_transcript.return_value = listen_session

        args = argparse.Namespace(title=None, date=None, meet=True, event_id=None)
        cmd_listen(agent, args)

        # The listener should have been started with the Meet session's title
        mock_listener.start.assert_called_once()
        call_kwargs = mock_listener.start.call_args
        assert call_kwargs[1]["meeting_title"] == "Q1 Strategy Review"
        assert call_kwargs[1]["meeting_date"] == "2026-03-28"

    def test_listen_with_meet_flag_no_session_found(self, tmp_path: Path):
        """When --meet is used but no session is found, falls back to defaults."""
        from digo.audio_listener import ListenSession

        agent = MagicMock()
        mock_listener = MagicMock()
        agent.create_listener.return_value = mock_listener
        agent.get_next_meet_session.return_value = None

        listen_session = ListenSession(meeting_title="Live Meeting", meeting_date="2026-03-28")
        mock_listener.is_listening = False
        mock_listener.stop.return_value = listen_session
        mock_listener.get_transcript.return_value = listen_session

        args = argparse.Namespace(title=None, date=None, meet=True, event_id=None)
        cmd_listen(agent, args)

        # Falls back to default title "Live Meeting"
        mock_listener.start.assert_called_once()

    def test_listen_with_event_id(self, tmp_path: Path):
        """When --event-id is used, fetches specific event."""
        from digo.audio_listener import ListenSession
        from digo.google_meet import MeetSession

        agent = MagicMock()
        mock_listener = MagicMock()
        agent.create_listener.return_value = mock_listener

        meet_session = MeetSession(
            title="Specific Meeting",
            meeting_date="2026-03-28",
            start_time="2026-03-28T14:00:00Z",
            end_time="2026-03-28T15:00:00Z",
            meet_link="https://meet.google.com/xyz-abcd-efg",
            calendar_event_id="specific-event",
        )
        agent.get_meet_session_by_event_id.return_value = meet_session

        listen_session = ListenSession(meeting_title="Specific Meeting", meeting_date="2026-03-28")
        mock_listener.is_listening = False
        mock_listener.stop.return_value = listen_session
        mock_listener.get_transcript.return_value = listen_session

        args = argparse.Namespace(title=None, date=None, meet=False, event_id="specific-event")
        cmd_listen(agent, args)

        agent.get_meet_session_by_event_id.assert_called_once_with("specific-event")
        mock_listener.start.assert_called_once()
        call_kwargs = mock_listener.start.call_args
        assert call_kwargs[1]["meeting_title"] == "Specific Meeting"

    def test_listen_title_overrides_meet_session(self, tmp_path: Path):
        """When both --meet and --title are used, --title takes precedence."""
        from digo.audio_listener import ListenSession
        from digo.google_meet import MeetSession

        agent = MagicMock()
        mock_listener = MagicMock()
        agent.create_listener.return_value = mock_listener

        meet_session = MeetSession(
            title="Meet Title",
            meeting_date="2026-03-28",
            start_time="2026-03-28T14:00:00Z",
            end_time="2026-03-28T15:00:00Z",
            meet_link="https://meet.google.com/abc-defg-hij",
            calendar_event_id="event123",
        )
        agent.get_next_meet_session.return_value = meet_session

        listen_session = ListenSession(meeting_title="Custom Title", meeting_date="2026-03-28")
        mock_listener.is_listening = False
        mock_listener.stop.return_value = listen_session
        mock_listener.get_transcript.return_value = listen_session

        args = argparse.Namespace(title="Custom Title", date=None, meet=True, event_id=None)
        cmd_listen(agent, args)

        mock_listener.start.assert_called_once()
        call_kwargs = mock_listener.start.call_args
        assert call_kwargs[1]["meeting_title"] == "Custom Title"


# ---------------------------------------------------------------------------
# notes command — mutual exclusion
# ---------------------------------------------------------------------------


class TestCmdNotesMutualExclusion:
    def test_notes_both_transcript_and_text_exits(self, tmp_path: Path):
        """Providing both --transcript and --text should fail."""
        f = tmp_path / "transcript.txt"
        f.write_text("Alice: Hello.", encoding="utf-8")

        agent = MagicMock()
        args = argparse.Namespace(
            transcript=str(f),
            text="Alice: Hello.",
            title="Test",
            date=None,
        )
        with pytest.raises(SystemExit):
            cmd_notes(agent, args)


# ---------------------------------------------------------------------------
# CFV CLI commands
# ---------------------------------------------------------------------------


class TestCmdCfvReport:
    def test_cfv_report_calls_agent(self):
        agent = MagicMock()
        agent.generate_cfv_report.return_value = "## CFV Report"
        args = argparse.Namespace()
        cmd_cfv_report(agent, args)
        agent.generate_cfv_report.assert_called_once()

    def test_cfv_report_empty_report(self):
        agent = MagicMock()
        agent.generate_cfv_report.return_value = "## CFV Daily Report — Data Unavailable"
        args = argparse.Namespace()
        cmd_cfv_report(agent, args)
        agent.generate_cfv_report.assert_called_once()


class TestCmdCfvSnapshot:
    def test_cfv_snapshot_with_coins(self):
        from digo.cfv_client import CFVCoinMetrics, CFVPortfolioSnapshot

        agent = MagicMock()
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
            api_url="http://localhost:3000",
        )
        agent.take_cfv_snapshot.return_value = snapshot
        args = argparse.Namespace()
        cmd_cfv_snapshot(agent, args)
        agent.take_cfv_snapshot.assert_called_once()

    def test_cfv_snapshot_no_coins(self):
        from digo.cfv_client import CFVPortfolioSnapshot

        agent = MagicMock()
        agent.take_cfv_snapshot.return_value = CFVPortfolioSnapshot()
        args = argparse.Namespace()
        cmd_cfv_snapshot(agent, args)
        agent.take_cfv_snapshot.assert_called_once()


class TestCmdCfvAlerts:
    def test_cfv_alerts_with_alerts(self):
        agent = MagicMock()
        agent.check_cfv_alerts.return_value = (
            [{"symbol": "BTC", "deviation_pct": 25.0}],
            "## Alerts\n\n⚠️ 1 alert",
        )
        args = argparse.Namespace()
        cmd_cfv_alerts(agent, args)
        agent.check_cfv_alerts.assert_called_once()

    def test_cfv_alerts_no_alerts(self):
        agent = MagicMock()
        agent.check_cfv_alerts.return_value = ([], "## No alerts")
        args = argparse.Namespace()
        cmd_cfv_alerts(agent, args)
        agent.check_cfv_alerts.assert_called_once()


class TestCmdCfvAnalysis:
    def test_cfv_analysis_calls_agent(self):
        agent = MagicMock()
        agent.generate_cfv_battle_plan_analysis.return_value = "## Analysis"
        args = argparse.Namespace()
        cmd_cfv_analysis(agent, args)
        agent.generate_cfv_battle_plan_analysis.assert_called_once()


# ---------------------------------------------------------------------------
# CFV parser tests
# ---------------------------------------------------------------------------


class TestBuildParserCfv:
    def test_cfv_report_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["cfv-report"])
        assert args.command == "cfv-report"

    def test_cfv_snapshot_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["cfv-snapshot"])
        assert args.command == "cfv-snapshot"

    def test_cfv_alerts_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["cfv-alerts"])
        assert args.command == "cfv-alerts"

    def test_cfv_analysis_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["cfv-analysis"])
        assert args.command == "cfv-analysis"


# ---------------------------------------------------------------------------
# listen command — device selection
# ---------------------------------------------------------------------------


class TestBuildParserListenDevice:
    def test_listen_device_flag(self):
        parser = build_parser()
        args = parser.parse_args(["listen", "--device", "Stereo Mix"])
        assert args.device == "Stereo Mix"

    def test_listen_device_default_none(self):
        parser = build_parser()
        args = parser.parse_args(["listen"])
        assert args.device is None

    def test_listen_list_devices_flag(self):
        parser = build_parser()
        args = parser.parse_args(["listen", "--list-devices"])
        assert args.list_devices is True

    def test_listen_list_devices_default_false(self):
        parser = build_parser()
        args = parser.parse_args(["listen"])
        assert args.list_devices is False


class TestCmdListenDevice:
    def test_list_devices_prints_and_returns(self):
        """--list-devices prints all devices and returns without starting listener."""
        agent = MagicMock()
        device_names = ["Microsoft Sound Mapper", "Microphone (Brio 101)", "Stereo Mix"]
        with patch(
            "speech_recognition.Microphone.list_microphone_names", return_value=device_names
        ):
            args = argparse.Namespace(
                list_devices=True,
                device=None,
                title=None,
                date=None,
                meet=False,
                event_id=None,
            )
            cmd_listen(agent, args)

        agent.create_listener.assert_not_called()

    def test_list_devices_import_error_exits(self):
        """If SpeechRecognition is missing, --list-devices exits with error."""
        agent = MagicMock()
        with patch.dict("sys.modules", {"speech_recognition": None}):
            args = argparse.Namespace(
                list_devices=True,
                device=None,
                title=None,
                date=None,
                meet=False,
                event_id=None,
            )
            with pytest.raises((SystemExit, ImportError)):
                cmd_listen(agent, args)

    def test_device_name_resolved_to_index(self):
        """When --device is given, the correct device_index is passed to create_listener."""
        from digo.audio_listener import ListenSession

        agent = MagicMock()
        mock_listener = MagicMock()
        agent.create_listener.return_value = mock_listener

        listen_session = ListenSession(meeting_title="Test", meeting_date="2026-04-01")
        mock_listener.is_listening = False
        mock_listener.stop.return_value = listen_session
        mock_listener.get_transcript.return_value = listen_session

        device_names = [
            "Microsoft Sound Mapper",
            "Microphone (Brio 101)",
            "Stereo Mix (Realtek HD Audio Stereo input)",
        ]
        with patch(
            "speech_recognition.Microphone.list_microphone_names", return_value=device_names
        ):
            args = argparse.Namespace(
                list_devices=False,
                device="Stereo Mix",
                title="Test",
                date="2026-04-01",
                meet=False,
                event_id=None,
            )
            cmd_listen(agent, args)

        agent.create_listener.assert_called_once_with(device_index=2)

    def test_device_name_not_found_exits(self):
        """When --device matches nothing, cmd_listen exits with an error."""
        agent = MagicMock()
        device_names = ["Microsoft Sound Mapper", "Microphone (Brio 101)"]
        with patch(
            "speech_recognition.Microphone.list_microphone_names", return_value=device_names
        ):
            args = argparse.Namespace(
                list_devices=False,
                device="Nonexistent Device",
                title="Test",
                date=None,
                meet=False,
                event_id=None,
            )
            with pytest.raises(SystemExit):
                cmd_listen(agent, args)

    def test_no_device_flag_uses_none_index(self):
        """When neither --device nor AUDIO_DEVICE is set, device_index=None."""
        from digo.audio_listener import ListenSession

        agent = MagicMock()
        mock_listener = MagicMock()
        agent.create_listener.return_value = mock_listener

        listen_session = ListenSession(meeting_title="Test", meeting_date="2026-04-01")
        mock_listener.is_listening = False
        mock_listener.stop.return_value = listen_session
        mock_listener.get_transcript.return_value = listen_session

        with patch("digo.cli.config") as mock_config:
            mock_config.AUDIO_DEVICE = ""
            args = argparse.Namespace(
                list_devices=False,
                device=None,
                title="Test",
                date="2026-04-01",
                meet=False,
                event_id=None,
            )
            cmd_listen(agent, args)

        agent.create_listener.assert_called_once_with(device_index=None)

    def test_audio_device_env_var_used_when_no_flag(self):
        """AUDIO_DEVICE env var is used when --device is not given."""
        from digo.audio_listener import ListenSession

        agent = MagicMock()
        mock_listener = MagicMock()
        agent.create_listener.return_value = mock_listener

        listen_session = ListenSession(meeting_title="Test", meeting_date="2026-04-01")
        mock_listener.is_listening = False
        mock_listener.stop.return_value = listen_session
        mock_listener.get_transcript.return_value = listen_session

        device_names = ["Microsoft Sound Mapper", "Stereo Mix (Realtek HD Audio)"]
        with (
            patch("speech_recognition.Microphone.list_microphone_names", return_value=device_names),
            patch("digo.cli.config") as mock_config,
        ):
            mock_config.AUDIO_DEVICE = "Stereo Mix"
            args = argparse.Namespace(
                list_devices=False,
                device=None,
                title="Test",
                date="2026-04-01",
                meet=False,
                event_id=None,
            )
            cmd_listen(agent, args)

        agent.create_listener.assert_called_once_with(device_index=1)

    def test_device_flag_overrides_env_var(self):
        """--device CLI flag takes precedence over AUDIO_DEVICE env var."""
        from digo.audio_listener import ListenSession

        agent = MagicMock()
        mock_listener = MagicMock()
        agent.create_listener.return_value = mock_listener

        listen_session = ListenSession(meeting_title="Test", meeting_date="2026-04-01")
        mock_listener.is_listening = False
        mock_listener.stop.return_value = listen_session
        mock_listener.get_transcript.return_value = listen_session

        device_names = ["Default Mic", "Stereo Mix", "Another Device"]
        with (
            patch("speech_recognition.Microphone.list_microphone_names", return_value=device_names),
            patch("digo.cli.config") as mock_config,
        ):
            mock_config.AUDIO_DEVICE = "Default Mic"
            args = argparse.Namespace(
                list_devices=False,
                device="Another Device",
                title="Test",
                date="2026-04-01",
                meet=False,
                event_id=None,
            )
            cmd_listen(agent, args)

        # Should use index 2 ("Another Device"), not index 0 ("Default Mic")
        agent.create_listener.assert_called_once_with(device_index=2)
