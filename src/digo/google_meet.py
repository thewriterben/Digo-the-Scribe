"""
Google Meet session discovery for Digo the Scribe.

Uses the Google Calendar API to find upcoming or in-progress Google Meet
sessions and extract meeting metadata (title, date, participants, Meet link).
This enables the ``listen`` command to auto-populate meeting details when
the ``--meet`` flag is used.

Requirements:
    - A valid Google OAuth2 credentials file (see google_auth.py)
    - The ``calendar.readonly`` scope must be authorised

Usage::

    from digo.google_meet import GoogleMeetClient

    client = GoogleMeetClient()
    meeting = client.get_next_meeting()
    if meeting:
        print(meeting.title, meeting.meet_link)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

# Guard imports for optional Google API dependencies
try:
    from googleapiclient.discovery import build

    _GOOGLE_API_AVAILABLE = True
except ImportError:
    _GOOGLE_API_AVAILABLE = False

_IMPORT_ERROR_MSG = (
    "Google Meet integration requires 'google-api-python-client'. "
    "Install it with: pip install google-api-python-client"
)


@dataclass
class MeetSession:
    """Metadata for a Google Meet session discovered via Google Calendar."""

    title: str
    meeting_date: str  # ISO-8601 date, e.g. "2026-03-28"
    start_time: str  # ISO-8601 datetime string
    end_time: str  # ISO-8601 datetime string
    meet_link: str  # e.g. "https://meet.google.com/abc-defg-hij"
    calendar_event_id: str
    participants: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Return a short human-readable summary of this session."""
        parts = [
            f"Title: {self.title}",
            f"Date: {self.meeting_date}",
            f"Start: {self.start_time}",
            f"End: {self.end_time}",
            f"Meet link: {self.meet_link}",
        ]
        if self.participants:
            parts.append(f"Participants: {', '.join(self.participants)}")
        return "\n".join(parts)


def _extract_meet_link(event: dict) -> str:
    """Extract the Google Meet link from a Calendar event, if present."""
    # Primary location: conferenceData
    conf_data = event.get("conferenceData", {})
    for entry_point in conf_data.get("entryPoints", []):
        if entry_point.get("entryPointType") == "video":
            uri = entry_point.get("uri", "")
            if "meet.google.com" in uri:
                return uri
    # Fallback: hangoutLink field
    hangout = event.get("hangoutLink", "")
    if "meet.google.com" in hangout:
        return hangout
    return ""


def _extract_participants(event: dict) -> list[str]:
    """Extract attendee display names / emails from a Calendar event."""
    attendees = event.get("attendees", [])
    participants: list[str] = []
    for attendee in attendees:
        name = attendee.get("displayName") or attendee.get("email", "")
        if name:
            participants.append(name)
    return participants


def _event_to_meet_session(event: dict) -> MeetSession | None:
    """Convert a Google Calendar event dict into a MeetSession, or None if not a Meet."""
    meet_link = _extract_meet_link(event)
    if not meet_link:
        return None

    start_raw = event.get("start", {})
    end_raw = event.get("end", {})
    start_dt_str = start_raw.get("dateTime", start_raw.get("date", ""))
    end_dt_str = end_raw.get("dateTime", end_raw.get("date", ""))

    # Extract date portion
    meeting_date = start_dt_str[:10] if start_dt_str else ""

    return MeetSession(
        title=event.get("summary", "Untitled Meeting"),
        meeting_date=meeting_date,
        start_time=start_dt_str,
        end_time=end_dt_str,
        meet_link=meet_link,
        calendar_event_id=event.get("id", ""),
        participants=_extract_participants(event),
    )


class GoogleMeetClient:
    """
    Discovers Google Meet sessions via the Google Calendar API.

    Requires valid Google OAuth2 credentials (see :mod:`digo.google_auth`).
    """

    def __init__(self) -> None:
        if not _GOOGLE_API_AVAILABLE:
            raise ImportError(_IMPORT_ERROR_MSG)
        self._service = None

    def _ensure_service(self) -> None:
        """Lazily build the Calendar API service."""
        if self._service is not None:
            return
        from digo.google_auth import get_credentials

        creds = get_credentials()
        self._service = build("calendar", "v3", credentials=creds)

    def get_upcoming_meetings(
        self,
        max_results: int = 5,
        look_ahead_hours: int = 24,
    ) -> list[MeetSession]:
        """
        Return upcoming Google Meet sessions from the user's primary calendar.

        Parameters
        ----------
        max_results:
            Maximum number of events to retrieve from the Calendar API.
        look_ahead_hours:
            How many hours ahead to look for events.

        Returns
        -------
        list[MeetSession]
            A list of upcoming Meet sessions, sorted by start time.
        """
        self._ensure_service()

        now = datetime.now(tz=UTC)
        time_min = now.isoformat()
        time_max = (now + timedelta(hours=look_ahead_hours)).isoformat()

        try:
            events_result = (
                self._service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                    conferenceDataVersion=1,
                )
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch calendar events")
            return []

        events = events_result.get("items", [])
        sessions: list[MeetSession] = []
        for event in events:
            session = _event_to_meet_session(event)
            if session is not None:
                sessions.append(session)
                logger.debug("Found Meet session: %s", session.title)

        logger.info("Found %d upcoming Google Meet session(s)", len(sessions))
        return sessions

    def get_next_meeting(self) -> MeetSession | None:
        """Return the next upcoming Google Meet session, or ``None``."""
        sessions = self.get_upcoming_meetings(max_results=10)
        return sessions[0] if sessions else None

    def get_meeting_by_event_id(self, event_id: str) -> MeetSession | None:
        """
        Fetch a specific Google Calendar event by ID and return it as a
        :class:`MeetSession` if it has a Google Meet link.
        """
        self._ensure_service()

        try:
            event = (
                self._service.events()
                .get(
                    calendarId="primary",
                    eventId=event_id,
                    conferenceDataVersion=1,
                )
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch calendar event %s", event_id)
            return None

        return _event_to_meet_session(event)
