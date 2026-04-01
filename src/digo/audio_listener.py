"""
Audio listener for Digo the Scribe.

Captures microphone audio and transcribes speech to text in real-time
using the SpeechRecognition library, enabling Digo to listen to live
meetings and build a transcript for note-taking.

Requirements:
    pip install SpeechRecognition PyAudio

Usage::

    from digo.audio_listener import AudioListener

    listener = AudioListener()
    listener.start("Q1 Strategy Review")

    # ... listener runs until stopped via Ctrl+C or stop() ...
    transcript = listener.get_transcript()
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Guard imports for optional audio dependencies
try:
    import speech_recognition as sr

    _SR_AVAILABLE = True
except ImportError:
    _SR_AVAILABLE = False

_IMPORT_ERROR_MSG = (
    "Audio listener requires 'SpeechRecognition' and 'PyAudio'. "
    "Install them with: pip install SpeechRecognition PyAudio"
)


@dataclass
class ListenSegment:
    """A single recognised speech segment from the microphone."""

    text: str
    timestamp: str  # ISO-8601 time, e.g. "14:30:05"
    confidence: float | None = None  # 0.0-1.0, None if not provided


@dataclass
class ListenSession:
    """Accumulates segments captured during a single listening session."""

    meeting_title: str
    meeting_date: str
    started_at: str = ""
    segments: list[ListenSegment] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def add_segment(self, segment: ListenSegment) -> None:
        with self._lock:
            self.segments.append(segment)

    def as_simple_transcript(self) -> str:
        """Return all segments formatted as a simple transcript string."""
        with self._lock:
            lines = []
            for seg in self.segments:
                lines.append(f"[{seg.timestamp}] Speaker: {seg.text}")
            return "\n".join(lines)

    @property
    def segment_count(self) -> int:
        with self._lock:
            return len(self.segments)


class AudioListener:
    """
    Captures microphone audio and transcribes speech in real-time.

    Uses the ``speech_recognition`` library to listen for speech via the
    default microphone and converts it to text using Google's free
    speech-to-text API (or a configurable recogniser).

    The listener runs in a background thread so the main thread remains
    responsive (e.g. for Ctrl+C handling).
    """

    def __init__(
        self,
        energy_threshold: int = 300,
        pause_threshold: float = 1.0,
        phrase_time_limit: float | None = 30.0,
        device_index: int | None = None,
    ) -> None:
        if not _SR_AVAILABLE:
            raise ImportError(_IMPORT_ERROR_MSG)

        self._recogniser = sr.Recognizer()
        self._recogniser.energy_threshold = energy_threshold
        self._recogniser.pause_threshold = pause_threshold
        self._phrase_time_limit = phrase_time_limit
        self._device_index = device_index
        self._session: ListenSession | None = None
        self._stop_event = threading.Event()
        self._listen_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        meeting_title: str,
        meeting_date: str = "",
    ) -> None:
        """
        Begin listening on the default microphone.

        Runs speech recognition in a background thread. Call :meth:`stop`
        or send KeyboardInterrupt to end the session.
        """
        if self._listen_thread and self._listen_thread.is_alive():
            raise RuntimeError("Listener is already running. Call stop() first.")

        date = meeting_date or datetime.now(tz=UTC).date().isoformat()
        now_time = datetime.now(tz=UTC).strftime("%H:%M:%S")

        self._session = ListenSession(
            meeting_title=meeting_title,
            meeting_date=date,
            started_at=now_time,
        )
        self._stop_event.clear()

        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="digo-audio-listener",
        )
        self._listen_thread.start()
        logger.info(
            "Audio listener started for '%s' at %s",
            meeting_title,
            now_time,
        )

    def stop(self) -> ListenSession:
        """
        Stop listening and return the accumulated session.

        Safe to call multiple times.
        """
        self._stop_event.set()
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=5.0)
        session = self._session
        if session is None:
            raise RuntimeError("No active listening session to stop.")
        logger.info(
            "Audio listener stopped. Captured %d segments.",
            session.segment_count,
        )
        return session

    @property
    def is_listening(self) -> bool:
        return (
            self._listen_thread is not None
            and self._listen_thread.is_alive()
            and not self._stop_event.is_set()
        )

    def get_transcript(self) -> ListenSession | None:
        """Return the current (or most recent) session, if any."""
        return self._session

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _listen_loop(self) -> None:
        """Background loop: capture audio → recognise → store segment."""
        try:
            mic = sr.Microphone(device_index=self._device_index)
        except (OSError, AttributeError):
            logger.error(
                "Could not access microphone. Ensure a microphone is connected "
                "and PyAudio is installed correctly."
            )
            self._stop_event.set()
            return

        with mic as source:
            logger.info("Adjusting for ambient noise…")
            self._recogniser.adjust_for_ambient_noise(source, duration=1)
            logger.info("Listening…")

            while not self._stop_event.is_set():
                try:
                    audio = self._recogniser.listen(
                        source,
                        timeout=2,
                        phrase_time_limit=self._phrase_time_limit,
                    )
                except sr.WaitTimeoutError:
                    # No speech detected within timeout — loop and try again
                    continue

                # Attempt recognition in a non-blocking way
                self._recognise_audio(audio)

    def _recognise_audio(self, audio: sr.AudioData) -> None:  # type: ignore[name-defined]
        """Send captured audio to the recogniser and store the result."""
        timestamp = datetime.now(tz=UTC).strftime("%H:%M:%S")
        try:
            result = self._recogniser.recognize_google(audio, show_all=False)
            if isinstance(result, str) and result.strip():
                segment = ListenSegment(
                    text=result.strip(),
                    timestamp=timestamp,
                )
                if self._session:
                    self._session.add_segment(segment)
                    logger.debug("[%s] %s", timestamp, result.strip())
        except sr.UnknownValueError:
            # Speech was unintelligible — skip
            logger.debug("[%s] (unintelligible audio, skipped)", timestamp)
        except sr.RequestError as exc:
            logger.warning("Speech recognition API error: %s", exc)
            # Brief pause to avoid hammering the API on repeated failures
            time.sleep(1)
