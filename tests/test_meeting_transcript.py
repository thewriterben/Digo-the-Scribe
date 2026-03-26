"""Tests for the meeting transcript handler."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from digo.meeting_transcript import (
    MeetingTranscript,
    TranscriptLine,
    load_transcript_from_file,
    load_transcript_from_text,
)


# ---------------------------------------------------------------------------
# TranscriptLine
# ---------------------------------------------------------------------------

class TestTranscriptLine:
    def test_formatted_with_timestamp(self):
        line = TranscriptLine(speaker="Alice", timestamp="00:01:23", text="Hello everyone.")
        assert line.formatted() == "[00:01:23] Alice: Hello everyone."

    def test_formatted_without_timestamp(self):
        line = TranscriptLine(speaker="Bob", timestamp=None, text="Good morning.")
        assert line.formatted() == "Bob: Good morning."


# ---------------------------------------------------------------------------
# MeetingTranscript
# ---------------------------------------------------------------------------

class TestMeetingTranscript:
    def _make_transcript(self) -> MeetingTranscript:
        return MeetingTranscript(
            meeting_title="Q1 Review",
            meeting_date="2026-03-26",
            lines=[
                TranscriptLine("Alice", "00:00:05", "Welcome to the meeting."),
                TranscriptLine("Bob", "00:00:15", "Thanks Alice."),
                TranscriptLine("Alice", "00:01:00", "Let's begin."),
            ],
        )

    def test_speakers_unique_ordered(self):
        t = self._make_transcript()
        assert t.speakers() == ["Alice", "Bob"]

    def test_full_text_contains_all_lines(self):
        t = self._make_transcript()
        text = t.full_text()
        assert "Welcome to the meeting." in text
        assert "Thanks Alice." in text
        assert "Let's begin." in text


# ---------------------------------------------------------------------------
# load_transcript_from_text
# ---------------------------------------------------------------------------

class TestLoadFromText:
    def test_simple_speaker_colon_format(self):
        raw = textwrap.dedent("""\
            Alice: We need to discuss the Battle Plan milestones.
            Bob: Agreed, let's cover phase one first.
        """)
        transcript = load_transcript_from_text(raw, meeting_title="Test")
        assert len(transcript.lines) == 2
        assert transcript.lines[0].speaker == "Alice"
        assert transcript.lines[1].speaker == "Bob"
        assert transcript.lines[0].timestamp is None

    def test_google_meet_timestamp_format(self):
        raw = textwrap.dedent("""\
            0:00:05 Benjamin Snider
            Good morning everyone, let's get started.
            0:00:30 Alice
            Good morning.
        """)
        transcript = load_transcript_from_text(raw, meeting_title="GMeet Test")
        assert len(transcript.lines) == 2
        assert transcript.lines[0].speaker == "Benjamin Snider"
        assert transcript.lines[0].timestamp == "0:00:05"
        assert "Good morning everyone" in transcript.lines[0].text

    def test_meeting_date_defaults_to_today(self):
        transcript = load_transcript_from_text("Alice: Hello.", meeting_title="T")
        import datetime
        assert transcript.meeting_date == datetime.date.today().isoformat()

    def test_empty_text_produces_empty_lines(self):
        transcript = load_transcript_from_text("", meeting_title="Empty")
        assert transcript.lines == []


# ---------------------------------------------------------------------------
# load_transcript_from_file
# ---------------------------------------------------------------------------

class TestLoadFromFile:
    def test_load_simple_txt_file(self, tmp_path: Path):
        f = tmp_path / "meeting.txt"
        f.write_text("Alice: Hello.\nBob: Hi there.\n", encoding="utf-8")
        transcript = load_transcript_from_file(f, meeting_title="File Test")
        assert len(transcript.lines) >= 1

    def test_load_json_file(self, tmp_path: Path):
        data = [
            {"speaker": "Alice", "timestamp": "00:00:05", "text": "Hello."},
            {"speaker": "Bob", "timestamp": "00:00:10", "text": "Hi."},
        ]
        f = tmp_path / "meeting.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        transcript = load_transcript_from_file(f)
        assert len(transcript.lines) == 2
        assert transcript.lines[0].speaker == "Alice"

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_transcript_from_file(Path("/nonexistent/path/transcript.txt"))
