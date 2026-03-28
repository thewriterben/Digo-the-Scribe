"""
Core Digo agent.

Orchestrates PDF loading, transcript processing, LLM calls, and report
generation.  The agent is deliberately conservative: it will always prefer
to flag uncertainty over producing a confident-sounding but potentially
incorrect answer.
"""

from __future__ import annotations

import logging
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from digo import config
from digo.audio_listener import AudioListener, ListenSession
from digo.meeting_transcript import (
    MeetingTranscript,
    load_transcript_from_file,
    load_transcript_from_text,
)
from digo.pdf_processor import ResourceLibrary
from digo.prompts import (
    ESCALATION_EMAIL_TEMPLATE,
    NOTE_TAKING_PROMPT_TEMPLATE,
    PROGRESS_REPORT_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# Document names used as keys in the ResourceLibrary
BATTLE_PLAN_KEY = "Battle Plan"
BEYOND_BITCOIN_KEY = "Beyond Bitcoin"
DIGITAL_GOLD_WHITE_PAPER_KEY = "Digital Gold White Paper"


class DigoAgent:
    """
    Digo the Scribe — Hyper Agent for Digital Gold Co meeting notes.

    Usage::

        agent = DigoAgent()
        agent.load_resources()          # load PDFs (when available)
        notes = agent.take_notes_from_file("path/to/transcript.txt",
                                           meeting_title="Q1 Strategy Review",
                                           meeting_date="2026-03-26")
        agent.save_notes(notes, "q1_strategy_review")
        report = agent.generate_progress_report(notes)
        agent.save_report(report, "q1_strategy_review")
    """

    def __init__(self) -> None:
        self._library = ResourceLibrary()
        self._llm: anthropic.Anthropic | None = None
        self._init_llm()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_llm(self) -> None:
        if not config.ANTHROPIC_API_KEY:
            logger.warning(
                "ANTHROPIC_API_KEY not set. LLM calls will not work until the key is provided."
            )
            return
        self._llm = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def load_resources(self) -> list[str]:
        """
        Attempt to load all reference PDFs.  Returns a list of warning
        messages for any document that could not be loaded (so the caller
        can surface these to the user rather than silently failing).
        """
        warnings: list[str] = []

        for key, path in (
            (BATTLE_PLAN_KEY, config.BATTLE_PLAN_PDF),
            (BEYOND_BITCOIN_KEY, config.BEYOND_BITCOIN_PDF),
            (DIGITAL_GOLD_WHITE_PAPER_KEY, config.DIGITAL_GOLD_WHITE_PAPER_PDF),
        ):
            try:
                self._library.load(key, path)
                logger.info("Loaded resource: %s", key)
            except FileNotFoundError as exc:
                msg = str(exc)
                logger.warning(msg)
                warnings.append(msg)

        return warnings

    def load_resource_from_path(self, name: str, path: Path) -> None:
        """Load an arbitrary PDF resource by name and path."""
        self._library.load(name, path)

    # ------------------------------------------------------------------
    # Live listening
    # ------------------------------------------------------------------

    def create_listener(
        self,
        energy_threshold: int = 300,
        pause_threshold: float = 1.0,
        phrase_time_limit: float | None = 30.0,
    ) -> AudioListener:
        """Create a new :class:`AudioListener` for live meeting capture."""
        return AudioListener(
            energy_threshold=energy_threshold,
            pause_threshold=pause_threshold,
            phrase_time_limit=phrase_time_limit,
        )

    def take_notes_from_session(self, session: ListenSession) -> str:
        """Process a completed :class:`ListenSession` into meeting notes."""
        raw_transcript = session.as_simple_transcript()
        if not raw_transcript.strip():
            return "*(No speech was captured during the listening session.)*"
        return self.take_notes_from_text(
            raw_transcript,
            meeting_title=session.meeting_title,
            meeting_date=session.meeting_date,
        )

    # ------------------------------------------------------------------
    # Note-taking
    # ------------------------------------------------------------------

    def take_notes_from_file(
        self,
        transcript_path: str | Path,
        meeting_title: str = "",
        meeting_date: str = "",
    ) -> str:
        transcript = load_transcript_from_file(
            Path(transcript_path),
            meeting_title=meeting_title,
            meeting_date=meeting_date,
        )
        return self._process_transcript(transcript)

    def take_notes_from_text(
        self,
        raw_transcript: str,
        meeting_title: str,
        meeting_date: str = "",
    ) -> str:
        transcript = load_transcript_from_text(
            raw_transcript,
            meeting_title=meeting_title,
            meeting_date=meeting_date,
        )
        return self._process_transcript(transcript)

    def _process_transcript(self, transcript: MeetingTranscript) -> str:
        """Core pipeline: extract relevant context, call LLM, return notes."""
        # Build Battle Plan, Beyond Bitcoin, and Digital Gold White Paper
        # excerpts relevant to the meeting
        battle_plan_excerpts = self._get_relevant_excerpts(BATTLE_PLAN_KEY, transcript.full_text())
        beyond_bitcoin_excerpts = self._get_relevant_excerpts(
            BEYOND_BITCOIN_KEY, transcript.full_text()
        )
        white_paper_excerpts = self._get_relevant_excerpts(
            DIGITAL_GOLD_WHITE_PAPER_KEY, transcript.full_text()
        )

        prompt = NOTE_TAKING_PROMPT_TEMPLATE.format(
            meeting_title=transcript.meeting_title,
            meeting_date=transcript.meeting_date,
            participants=", ".join(transcript.speakers()) or "Not specified",
            transcript=transcript.full_text(),
            document_status=self._library.status(),
            battle_plan_excerpts=battle_plan_excerpts,
            beyond_bitcoin_excerpts=beyond_bitcoin_excerpts,
            white_paper_excerpts=white_paper_excerpts,
        )

        notes = self._call_llm(prompt)
        return notes

    # ------------------------------------------------------------------
    # Progress reports
    # ------------------------------------------------------------------

    def generate_progress_report(self, meeting_notes: str) -> str:
        """Generate a progress report from existing meeting notes."""
        battle_plan_excerpts = self._get_relevant_excerpts(BATTLE_PLAN_KEY, meeting_notes)

        prompt = PROGRESS_REPORT_PROMPT_TEMPLATE.format(
            meeting_notes=meeting_notes,
            battle_plan_excerpts=battle_plan_excerpts,
        )
        return self._call_llm(prompt)

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------

    def create_escalation_notice(
        self,
        topic: str,
        context: str,
        reason: str,
        meeting_title: str,
        meeting_date: str = "",
    ) -> str:
        """
        Return a formatted escalation notice to be sent to the Operations
        Manager when Digo cannot confirm information.
        """
        date = meeting_date or datetime.now(tz=UTC).date().isoformat()
        return ESCALATION_EMAIL_TEMPLATE.format(
            ops_manager_name=config.OPS_MANAGER_NAME,
            topic=topic,
            meeting_title=meeting_title,
            meeting_date=date,
            context=textwrap.indent(context, "  "),
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_notes(self, notes: str, slug: str) -> Path:
        """Save meeting notes to the output/notes directory."""
        config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        out_path = config.NOTES_DIR / f"{date_str}_{slug}.md"
        out_path.write_text(notes, encoding="utf-8")
        logger.info("Notes saved to %s", out_path)
        return out_path

    def save_report(self, report: str, slug: str) -> Path:
        """Save a progress report to the output/reports directory."""
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        out_path = config.REPORTS_DIR / f"{date_str}_{slug}_report.md"
        out_path.write_text(report, encoding="utf-8")
        logger.info("Report saved to %s", out_path)
        return out_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_relevant_excerpts(self, doc_key: str, query: str) -> str:
        """
        Retrieve the most relevant passages from *doc_key* for *query*.
        Returns a formatted string ready for inclusion in an LLM prompt.
        If the document is not loaded, returns a clear notice.
        """
        doc = self._library.get(doc_key)
        if doc is None:
            return (
                f"[{doc_key} has not been loaded yet. "
                "Please provide the PDF file and reload resources.]"
            )

        chunks = doc.search(query, max_results=5)
        if not chunks:
            return f"[No relevant passages found in {doc_key} for this query.]"

        parts: list[str] = []
        for chunk in chunks:
            excerpt = textwrap.shorten(chunk.text, width=800, placeholder="…")
            parts.append(f"**{chunk.reference}**\n> {excerpt}")
        return "\n\n".join(parts)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_llm(self, user_prompt: str) -> str:
        """Send a prompt to the LLM and return the response text."""
        if self._llm is None:
            raise RuntimeError(
                "LLM client not initialised. Please set ANTHROPIC_API_KEY in your environment."
            )

        response = self._llm.messages.create(
            model=config.LLM_MODEL,
            max_tokens=config.LLM_MAX_TOKENS,
            temperature=config.LLM_TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract text from response
        text_blocks = [block.text for block in response.content if hasattr(block, "text")]
        return "\n".join(text_blocks)

    # ------------------------------------------------------------------
    # Status / diagnostics
    # ------------------------------------------------------------------

    def status(self) -> str:
        """Return a human-readable status summary."""
        lines = [
            "=== Digo the Scribe — Status ===",
            f"LLM model : {config.LLM_MODEL}",
            f"LLM ready : {'yes' if self._llm is not None else 'NO — ANTHROPIC_API_KEY missing'}",
            "",
            self._library.status(),
        ]
        warnings = config.validate()
        if warnings:
            lines += ["", "Configuration warnings:"]
            for w in warnings:
                lines.append(f"  ⚠  {w}")
        return "\n".join(lines)
