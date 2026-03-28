"""Tests for the Google Meet session discovery module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from digo.google_meet import (
    GoogleMeetClient,
    MeetSession,
    _event_to_meet_session,
    _extract_meet_link,
    _extract_participants,
    _is_google_meet_url,
)

# ---------------------------------------------------------------------------
# MeetSession dataclass
# ---------------------------------------------------------------------------


class TestMeetSession:
    def test_basic_session(self):
        session = MeetSession(
            title="Q1 Strategy Review",
            meeting_date="2026-03-28",
            start_time="2026-03-28T14:00:00Z",
            end_time="2026-03-28T15:00:00Z",
            meet_link="https://meet.google.com/abc-defg-hij",
            calendar_event_id="event123",
        )
        assert session.title == "Q1 Strategy Review"
        assert session.meeting_date == "2026-03-28"
        assert session.meet_link == "https://meet.google.com/abc-defg-hij"
        assert session.participants == []

    def test_session_with_participants(self):
        session = MeetSession(
            title="Team Sync",
            meeting_date="2026-03-28",
            start_time="2026-03-28T10:00:00Z",
            end_time="2026-03-28T10:30:00Z",
            meet_link="https://meet.google.com/xyz-abcd-efg",
            calendar_event_id="event456",
            participants=["Alice", "Bob", "Charlie"],
        )
        assert len(session.participants) == 3
        assert "Alice" in session.participants

    def test_summary(self):
        session = MeetSession(
            title="Weekly Standup",
            meeting_date="2026-03-28",
            start_time="2026-03-28T09:00:00Z",
            end_time="2026-03-28T09:30:00Z",
            meet_link="https://meet.google.com/aaa-bbbb-ccc",
            calendar_event_id="event789",
            participants=["Alice", "Bob"],
        )
        summary = session.summary()
        assert "Weekly Standup" in summary
        assert "2026-03-28" in summary
        assert "meet.google.com" in summary
        assert "Alice" in summary
        assert "Bob" in summary

    def test_summary_no_participants(self):
        session = MeetSession(
            title="Solo Call",
            meeting_date="2026-03-28",
            start_time="2026-03-28T09:00:00Z",
            end_time="2026-03-28T09:30:00Z",
            meet_link="https://meet.google.com/xxx-yyyy-zzz",
            calendar_event_id="event000",
        )
        summary = session.summary()
        assert "Participants" not in summary


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestIsGoogleMeetUrl:
    def test_valid_https_meet_url(self):
        assert _is_google_meet_url("https://meet.google.com/abc-defg-hij") is True

    def test_valid_http_meet_url(self):
        assert _is_google_meet_url("http://meet.google.com/abc-defg-hij") is True

    def test_invalid_subdomain(self):
        assert _is_google_meet_url("https://evil-meet.google.com/abc") is False

    def test_meet_in_path_only(self):
        assert _is_google_meet_url("https://evil.com/meet.google.com") is False

    def test_empty_string(self):
        assert _is_google_meet_url("") is False

    def test_non_url_string(self):
        assert _is_google_meet_url("not a url") is False

    def test_zoom_url(self):
        assert _is_google_meet_url("https://zoom.us/j/12345") is False


class TestExtractMeetLink:
    def test_from_conference_data(self):
        event = {
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/abc-defg-hij",
                    }
                ]
            }
        }
        assert _extract_meet_link(event) == "https://meet.google.com/abc-defg-hij"

    def test_from_hangout_link(self):
        event = {"hangoutLink": "https://meet.google.com/xyz-abcd-efg"}
        assert _extract_meet_link(event) == "https://meet.google.com/xyz-abcd-efg"

    def test_conference_data_takes_priority(self):
        event = {
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/aaa-bbbb-ccc",
                    }
                ]
            },
            "hangoutLink": "https://meet.google.com/xxx-yyyy-zzz",
        }
        assert _extract_meet_link(event) == "https://meet.google.com/aaa-bbbb-ccc"

    def test_no_meet_link(self):
        event = {"summary": "No Meet event"}
        assert _extract_meet_link(event) == ""

    def test_non_meet_video_entry(self):
        event = {
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://zoom.us/j/12345",
                    }
                ]
            }
        }
        assert _extract_meet_link(event) == ""

    def test_phone_entry_point_ignored(self):
        event = {
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "phone",
                        "uri": "tel:+1-555-123-4567",
                    },
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/abc-defg-hij",
                    },
                ]
            }
        }
        assert _extract_meet_link(event) == "https://meet.google.com/abc-defg-hij"


class TestExtractParticipants:
    def test_with_display_names(self):
        event = {
            "attendees": [
                {"displayName": "Alice", "email": "alice@example.com"},
                {"displayName": "Bob", "email": "bob@example.com"},
            ]
        }
        participants = _extract_participants(event)
        assert participants == ["Alice", "Bob"]

    def test_falls_back_to_email(self):
        event = {
            "attendees": [
                {"email": "alice@example.com"},
                {"displayName": "Bob", "email": "bob@example.com"},
            ]
        }
        participants = _extract_participants(event)
        assert participants == ["alice@example.com", "Bob"]

    def test_no_attendees(self):
        event = {"summary": "Solo event"}
        assert _extract_participants(event) == []

    def test_empty_attendees(self):
        event = {"attendees": []}
        assert _extract_participants(event) == []


class TestEventToMeetSession:
    def test_valid_meet_event(self):
        event = {
            "id": "event123",
            "summary": "Q1 Strategy Review",
            "start": {"dateTime": "2026-03-28T14:00:00Z"},
            "end": {"dateTime": "2026-03-28T15:00:00Z"},
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
            "attendees": [
                {"displayName": "Alice", "email": "alice@example.com"},
            ],
        }
        session = _event_to_meet_session(event)
        assert session is not None
        assert session.title == "Q1 Strategy Review"
        assert session.meeting_date == "2026-03-28"
        assert session.meet_link == "https://meet.google.com/abc-defg-hij"
        assert session.calendar_event_id == "event123"
        assert session.participants == ["Alice"]

    def test_event_without_meet_link_returns_none(self):
        event = {
            "id": "event456",
            "summary": "Lunch",
            "start": {"dateTime": "2026-03-28T12:00:00Z"},
            "end": {"dateTime": "2026-03-28T13:00:00Z"},
        }
        assert _event_to_meet_session(event) is None

    def test_event_with_date_only(self):
        event = {
            "id": "event789",
            "summary": "All Day Meet",
            "start": {"date": "2026-03-28"},
            "end": {"date": "2026-03-29"},
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
        }
        session = _event_to_meet_session(event)
        assert session is not None
        assert session.meeting_date == "2026-03-28"

    def test_event_without_summary(self):
        event = {
            "id": "event000",
            "start": {"dateTime": "2026-03-28T14:00:00Z"},
            "end": {"dateTime": "2026-03-28T15:00:00Z"},
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
        }
        session = _event_to_meet_session(event)
        assert session is not None
        assert session.title == "Untitled Meeting"


# ---------------------------------------------------------------------------
# GoogleMeetClient — construction
# ---------------------------------------------------------------------------


class TestGoogleMeetClientInit:
    def test_client_creation(self):
        client = GoogleMeetClient()
        assert client._service is None

    def test_import_error_when_google_api_missing(self):
        with (
            patch("digo.google_meet._GOOGLE_API_AVAILABLE", False),
            pytest.raises(ImportError, match="google-api-python-client"),
        ):
            GoogleMeetClient()


# ---------------------------------------------------------------------------
# GoogleMeetClient — API calls (mocked)
# ---------------------------------------------------------------------------


def _make_mock_service(events: list[dict] | None = None):
    """Create a mock Google Calendar service."""
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_service.events.return_value = mock_events

    # For list()
    mock_list = MagicMock()
    mock_events.list.return_value = mock_list
    mock_list.execute.return_value = {"items": events or []}

    # For get()
    mock_get = MagicMock()
    mock_events.get.return_value = mock_get
    if events:
        mock_get.execute.return_value = events[0]
    else:
        mock_get.execute.return_value = {}

    return mock_service


class TestGoogleMeetClientGetUpcoming:
    def test_returns_meet_sessions(self):
        events = [
            {
                "id": "event1",
                "summary": "Team Standup",
                "start": {"dateTime": "2026-03-28T09:00:00Z"},
                "end": {"dateTime": "2026-03-28T09:30:00Z"},
                "hangoutLink": "https://meet.google.com/aaa-bbbb-ccc",
            },
            {
                "id": "event2",
                "summary": "Lunch Break",
                "start": {"dateTime": "2026-03-28T12:00:00Z"},
                "end": {"dateTime": "2026-03-28T13:00:00Z"},
                # No Meet link
            },
            {
                "id": "event3",
                "summary": "Strategy Review",
                "start": {"dateTime": "2026-03-28T14:00:00Z"},
                "end": {"dateTime": "2026-03-28T15:00:00Z"},
                "hangoutLink": "https://meet.google.com/ddd-eeee-fff",
            },
        ]
        client = GoogleMeetClient()
        client._service = _make_mock_service(events)

        sessions = client.get_upcoming_meetings()
        assert len(sessions) == 2
        assert sessions[0].title == "Team Standup"
        assert sessions[1].title == "Strategy Review"

    def test_returns_empty_list_when_no_meets(self):
        events = [
            {
                "id": "event1",
                "summary": "No Meet Event",
                "start": {"dateTime": "2026-03-28T09:00:00Z"},
                "end": {"dateTime": "2026-03-28T10:00:00Z"},
            }
        ]
        client = GoogleMeetClient()
        client._service = _make_mock_service(events)

        sessions = client.get_upcoming_meetings()
        assert sessions == []

    def test_handles_api_error(self):
        client = GoogleMeetClient()
        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.side_effect = Exception(
            "API error"
        )
        client._service = mock_service

        sessions = client.get_upcoming_meetings()
        assert sessions == []


class TestGoogleMeetClientGetNext:
    def test_returns_first_session(self):
        events = [
            {
                "id": "event1",
                "summary": "First Meet",
                "start": {"dateTime": "2026-03-28T09:00:00Z"},
                "end": {"dateTime": "2026-03-28T09:30:00Z"},
                "hangoutLink": "https://meet.google.com/aaa-bbbb-ccc",
            },
        ]
        client = GoogleMeetClient()
        client._service = _make_mock_service(events)

        session = client.get_next_meeting()
        assert session is not None
        assert session.title == "First Meet"

    def test_returns_none_when_no_meets(self):
        client = GoogleMeetClient()
        client._service = _make_mock_service([])

        assert client.get_next_meeting() is None


class TestGoogleMeetClientGetByEventId:
    def test_returns_session_for_valid_event(self):
        event = {
            "id": "specific-event",
            "summary": "Specific Meeting",
            "start": {"dateTime": "2026-03-28T14:00:00Z"},
            "end": {"dateTime": "2026-03-28T15:00:00Z"},
            "hangoutLink": "https://meet.google.com/xxx-yyyy-zzz",
            "attendees": [{"displayName": "Ben", "email": "ben@example.com"}],
        }
        client = GoogleMeetClient()
        client._service = _make_mock_service([event])

        session = client.get_meeting_by_event_id("specific-event")
        assert session is not None
        assert session.title == "Specific Meeting"
        assert session.participants == ["Ben"]

    def test_returns_none_for_non_meet_event(self):
        event = {
            "id": "no-meet",
            "summary": "Lunch",
            "start": {"dateTime": "2026-03-28T12:00:00Z"},
            "end": {"dateTime": "2026-03-28T13:00:00Z"},
        }
        client = GoogleMeetClient()
        client._service = _make_mock_service([event])

        assert client.get_meeting_by_event_id("no-meet") is None

    def test_handles_api_error(self):
        client = GoogleMeetClient()
        mock_service = MagicMock()
        mock_service.events.return_value.get.return_value.execute.side_effect = Exception(
            "Not found"
        )
        client._service = mock_service

        assert client.get_meeting_by_event_id("bad-id") is None
