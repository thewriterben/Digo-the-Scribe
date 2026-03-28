"""Tests for the audio listener module."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from digo.audio_listener import (
    _SR_AVAILABLE,
    AudioListener,
    ListenSegment,
    ListenSession,
)

# ---------------------------------------------------------------------------
# ListenSegment
# ---------------------------------------------------------------------------


class TestListenSegment:
    def test_basic_segment(self):
        seg = ListenSegment(text="Hello everyone.", timestamp="14:30:05")
        assert seg.text == "Hello everyone."
        assert seg.timestamp == "14:30:05"
        assert seg.confidence is None

    def test_segment_with_confidence(self):
        seg = ListenSegment(text="Welcome.", timestamp="14:30:10", confidence=0.95)
        assert seg.confidence == 0.95


# ---------------------------------------------------------------------------
# ListenSession
# ---------------------------------------------------------------------------


class TestListenSession:
    def test_empty_session(self):
        session = ListenSession(meeting_title="Test", meeting_date="2026-03-28")
        assert session.segment_count == 0
        assert session.as_simple_transcript() == ""

    def test_add_segment(self):
        session = ListenSession(meeting_title="Test", meeting_date="2026-03-28")
        seg = ListenSegment(text="Hello.", timestamp="14:00:00")
        session.add_segment(seg)
        assert session.segment_count == 1
        assert "Hello." in session.as_simple_transcript()

    def test_transcript_format(self):
        session = ListenSession(meeting_title="Test", meeting_date="2026-03-28")
        session.add_segment(ListenSegment(text="First line.", timestamp="14:00:00"))
        session.add_segment(ListenSegment(text="Second line.", timestamp="14:00:05"))
        transcript = session.as_simple_transcript()
        assert "[14:00:00] Speaker: First line." in transcript
        assert "[14:00:05] Speaker: Second line." in transcript

    def test_thread_safety(self):
        """Verify segments can be added from multiple threads."""
        session = ListenSession(meeting_title="Test", meeting_date="2026-03-28")

        def add_segments(start: int) -> None:
            for i in range(10):
                session.add_segment(
                    ListenSegment(text=f"Segment {start + i}", timestamp=f"14:00:{start + i:02d}")
                )

        threads = [threading.Thread(target=add_segments, args=(i * 10,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert session.segment_count == 30


# ---------------------------------------------------------------------------
# AudioListener — construction
# ---------------------------------------------------------------------------


class TestAudioListenerInit:
    @pytest.mark.skipif(not _SR_AVAILABLE, reason="SpeechRecognition not installed")
    def test_listener_creation(self):
        listener = AudioListener()
        assert not listener.is_listening

    @pytest.mark.skipif(not _SR_AVAILABLE, reason="SpeechRecognition not installed")
    def test_listener_custom_params(self):
        listener = AudioListener(
            energy_threshold=500,
            pause_threshold=2.0,
            phrase_time_limit=15.0,
        )
        assert listener._recogniser.energy_threshold == 500
        assert listener._recogniser.pause_threshold == 2.0
        assert listener._phrase_time_limit == 15.0


# ---------------------------------------------------------------------------
# AudioListener — start / stop lifecycle
# ---------------------------------------------------------------------------


class TestAudioListenerLifecycle:
    @pytest.mark.skipif(not _SR_AVAILABLE, reason="SpeechRecognition not installed")
    def test_start_and_stop(self):
        """Test basic start/stop lifecycle with mocked microphone."""
        listener = AudioListener()

        # Mock the listen loop so it doesn't actually access a microphone
        with patch.object(listener, "_listen_loop"):
            listener.start(meeting_title="Test Meeting", meeting_date="2026-03-28")
            assert listener.get_transcript() is not None
            assert listener.get_transcript().meeting_title == "Test Meeting"

            session = listener.stop()
            assert session.meeting_title == "Test Meeting"
            assert session.meeting_date == "2026-03-28"

    @pytest.mark.skipif(not _SR_AVAILABLE, reason="SpeechRecognition not installed")
    def test_stop_without_start_raises(self):
        listener = AudioListener()
        with pytest.raises(RuntimeError, match="No active listening session"):
            listener.stop()

    @pytest.mark.skipif(not _SR_AVAILABLE, reason="SpeechRecognition not installed")
    def test_double_start_raises(self):
        listener = AudioListener()

        # Make _listen_loop block until stop is called
        def blocking_loop():
            listener._stop_event.wait()

        with patch.object(listener, "_listen_loop", side_effect=blocking_loop):
            listener.start(meeting_title="Meeting 1")
            with pytest.raises(RuntimeError, match="already running"):
                listener.start(meeting_title="Meeting 2")
            listener.stop()

    @pytest.mark.skipif(not _SR_AVAILABLE, reason="SpeechRecognition not installed")
    def test_date_defaults_to_today(self):
        import datetime

        listener = AudioListener()
        with patch.object(listener, "_listen_loop"):
            listener.start(meeting_title="Test")
            session = listener.stop()
            assert session.meeting_date == datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# AudioListener — recognition
# ---------------------------------------------------------------------------


class TestAudioListenerRecognition:
    @pytest.mark.skipif(not _SR_AVAILABLE, reason="SpeechRecognition not installed")
    def test_recognise_audio_stores_segment(self):
        """When recognition succeeds, a segment is added to the session."""
        import speech_recognition as sr

        listener = AudioListener()
        listener._session = ListenSession(meeting_title="Test", meeting_date="2026-03-28")

        mock_audio = MagicMock(spec=sr.AudioData)
        with patch.object(listener._recogniser, "recognize_google", return_value="Hello everyone"):
            listener._recognise_audio(mock_audio)

        assert listener._session.segment_count == 1
        assert listener._session.segments[0].text == "Hello everyone"

    @pytest.mark.skipif(not _SR_AVAILABLE, reason="SpeechRecognition not installed")
    def test_recognise_audio_handles_unknown_value(self):
        """When speech is unintelligible, no segment is added."""
        import speech_recognition as sr

        listener = AudioListener()
        listener._session = ListenSession(meeting_title="Test", meeting_date="2026-03-28")

        mock_audio = MagicMock(spec=sr.AudioData)
        with patch.object(
            listener._recogniser,
            "recognize_google",
            side_effect=sr.UnknownValueError(),
        ):
            listener._recognise_audio(mock_audio)

        assert listener._session.segment_count == 0

    @pytest.mark.skipif(not _SR_AVAILABLE, reason="SpeechRecognition not installed")
    def test_recognise_audio_handles_request_error(self):
        """When the API fails, no segment is added and no exception raised."""
        import speech_recognition as sr

        listener = AudioListener()
        listener._session = ListenSession(meeting_title="Test", meeting_date="2026-03-28")

        mock_audio = MagicMock(spec=sr.AudioData)
        with (
            patch.object(
                listener._recogniser,
                "recognize_google",
                side_effect=sr.RequestError("API unavailable"),
            ),
            patch("digo.audio_listener.time.sleep"),
        ):
            listener._recognise_audio(mock_audio)

        assert listener._session.segment_count == 0

    @pytest.mark.skipif(not _SR_AVAILABLE, reason="SpeechRecognition not installed")
    def test_recognise_audio_skips_empty_result(self):
        """Empty recognition results are not stored."""
        import speech_recognition as sr

        listener = AudioListener()
        listener._session = ListenSession(meeting_title="Test", meeting_date="2026-03-28")

        mock_audio = MagicMock(spec=sr.AudioData)
        with patch.object(listener._recogniser, "recognize_google", return_value="   "):
            listener._recognise_audio(mock_audio)

        assert listener._session.segment_count == 0


# ---------------------------------------------------------------------------
# AudioListener — import guard
# ---------------------------------------------------------------------------


class TestImportGuard:
    def test_import_error_when_sr_missing(self):
        """If SpeechRecognition is unavailable, constructing raises ImportError."""
        with (
            patch("digo.audio_listener._SR_AVAILABLE", False),
            pytest.raises(ImportError, match="SpeechRecognition"),
        ):
            AudioListener()
