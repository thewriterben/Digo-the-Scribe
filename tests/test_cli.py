"""Tests for the CLI interface."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from digo.cli import (
    build_parser,
    cmd_escalate,
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
