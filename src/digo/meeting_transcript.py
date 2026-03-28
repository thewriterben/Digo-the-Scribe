"""
Meeting transcript handler for Digo the Scribe.

Supports two input modes:
  1. **File** — a plain-text or JSON transcript file saved after (or during)
     a Google Meet session.  Google Workspace Business/Enterprise accounts can
     export auto-generated captions as a .txt file.
  2. **Text** — a raw string passed directly (e.g. from a paste or pipe).

The handler normalises input into a list of :class:`TranscriptLine` objects
that the core agent then processes.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TranscriptLine:
    """One utterance from the meeting transcript."""

    speaker: str
    timestamp: str | None  # e.g. "00:03:15" — None if not available
    text: str

    def formatted(self) -> str:
        ts = f"[{self.timestamp}] " if self.timestamp else ""
        return f"{ts}{self.speaker}: {self.text}"


@dataclass
class MeetingTranscript:
    """All lines from a single meeting session."""

    meeting_title: str
    meeting_date: str  # ISO-8601 date string, e.g. "2026-03-26"
    participants: list[str] = field(default_factory=list)
    lines: list[TranscriptLine] = field(default_factory=list)

    def full_text(self) -> str:
        return "\n".join(line.formatted() for line in self.lines)

    def speakers(self) -> list[str]:
        seen: list[str] = []
        for line in self.lines:
            if line.speaker not in seen:
                seen.append(line.speaker)
        return seen


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

# Google Meet caption export format (approximate):
#   00:00:05 Speaker Name\n
#   Some spoken text.\n
_GMEET_LINE_RE = re.compile(r"^(?P<timestamp>\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<speaker>.+?)$")


def _parse_google_meet_txt(raw: str) -> list[TranscriptLine]:
    """
    Parse the plain-text caption format exported by Google Meet.

    Google Meet exports captions as:
        HH:MM:SS Speaker Name
        Spoken text

    Each utterance is a timestamp + speaker line followed by one or more
    lines of text.
    """
    lines_out: list[TranscriptLine] = []
    raw_lines = [line.rstrip() for line in raw.splitlines()]

    i = 0
    while i < len(raw_lines):
        m = _GMEET_LINE_RE.match(raw_lines[i])
        if m:
            timestamp = m.group("timestamp")
            speaker = m.group("speaker").strip()
            text_parts: list[str] = []
            i += 1
            while i < len(raw_lines) and not _GMEET_LINE_RE.match(raw_lines[i]):
                if raw_lines[i]:
                    text_parts.append(raw_lines[i])
                i += 1
            text = " ".join(text_parts).strip()
            if text:
                lines_out.append(TranscriptLine(speaker=speaker, timestamp=timestamp, text=text))
        else:
            i += 1

    return lines_out


def _parse_simple_txt(raw: str) -> list[TranscriptLine]:
    """
    Parse a simple "Speaker: text" transcript format (no timestamps).
    """
    lines_out: list[TranscriptLine] = []
    for raw_line in raw.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        if ":" in raw_line:
            speaker, _, text = raw_line.partition(":")
            speaker = speaker.strip()
            text = text.strip()
            if speaker and text:
                lines_out.append(TranscriptLine(speaker=speaker, timestamp=None, text=text))
        else:
            lines_out.append(TranscriptLine(speaker="[Unknown]", timestamp=None, text=raw_line))
    return lines_out


def _parse_json_transcript(raw: str) -> list[TranscriptLine]:
    """
    Parse a JSON transcript (custom or third-party format).

    Accepted shapes:
      [{"speaker": "...", "timestamp": "...", "text": "..."}, ...]
      [{"name": "...", "time": "...", "message": "..."}, ...]
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON transcript — falling back to empty.")
        return []

    if not isinstance(data, list):
        logger.warning("JSON transcript is not a list — falling back to empty.")
        return []

    lines_out: list[TranscriptLine] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        speaker = item.get("speaker") or item.get("name") or "[Unknown]"
        timestamp = item.get("timestamp") or item.get("time")
        text = item.get("text") or item.get("message") or ""
        if text:
            lines_out.append(
                TranscriptLine(speaker=str(speaker), timestamp=timestamp, text=str(text))
            )
    return lines_out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_transcript_from_file(
    path: Path,
    meeting_title: str = "",
    meeting_date: str = "",
) -> MeetingTranscript:
    """Load a transcript from *path* (auto-detects format from extension)."""
    if not path.exists():
        raise FileNotFoundError(f"Transcript file not found: {path}")

    raw = path.read_text(encoding="utf-8", errors="replace")
    title = meeting_title or path.stem
    date = meeting_date or datetime.now(tz=UTC).date().isoformat()

    if path.suffix.lower() == ".json":
        lines = _parse_json_transcript(raw)
    else:
        # Try Google Meet format first, fall back to simple
        lines = _parse_google_meet_txt(raw)
        if not lines:
            lines = _parse_simple_txt(raw)

    transcript = MeetingTranscript(
        meeting_title=title,
        meeting_date=date,
        lines=lines,
    )
    logger.info(
        "Loaded transcript '%s' (%s): %d lines, %d speakers",
        title,
        date,
        len(lines),
        len(transcript.speakers()),
    )
    return transcript


def load_transcript_from_text(
    raw: str,
    meeting_title: str,
    meeting_date: str = "",
) -> MeetingTranscript:
    """Parse a transcript provided as a raw string."""
    date = meeting_date or datetime.now(tz=UTC).date().isoformat()

    lines = _parse_google_meet_txt(raw)
    if not lines:
        lines = _parse_simple_txt(raw)

    return MeetingTranscript(
        meeting_title=meeting_title,
        meeting_date=date,
        lines=lines,
    )
