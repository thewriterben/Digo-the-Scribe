"""
Digo the Scribe — Hyper Agent for Digital Gold Co meeting notes.

Digo listens to Google Meet sessions and produces accurate, structured notes
cross-referenced against the Digital Gold Co Battle Plan.  When Digo cannot
fully confirm the validity of information it escalates to Operations Manager
Benjamin J. Snider rather than guessing.
"""

from __future__ import annotations

__version__ = "0.2.0"
__author__ = "Digital Gold Co / thewriterben"

from digo.agent import DigoAgent
from digo.audio_listener import AudioListener, ListenSegment, ListenSession
from digo.cfv_client import (
    CFVClient,
    CFVCoinMetrics,
    CFVCollectorHealth,
    CFVComponentMetrics,
    CFVPortfolioSnapshot,
)
from digo.cfv_data_store import CFVDataStore
from digo.cfv_reporter import CFVReporter, format_snapshot_summary
from digo.google_meet import GoogleMeetClient, MeetSession
from digo.meeting_transcript import (
    MeetingTranscript,
    load_transcript_from_file,
    load_transcript_from_text,
)
from digo.pdf_processor import DocumentChunk, IndexedDocument, ResourceLibrary

__all__ = [
    "AudioListener",
    "CFVClient",
    "CFVCoinMetrics",
    "CFVCollectorHealth",
    "CFVComponentMetrics",
    "CFVDataStore",
    "CFVPortfolioSnapshot",
    "CFVReporter",
    "DigoAgent",
    "DocumentChunk",
    "GoogleMeetClient",
    "IndexedDocument",
    "ListenSegment",
    "ListenSession",
    "MeetSession",
    "MeetingTranscript",
    "ResourceLibrary",
    "format_snapshot_summary",
    "load_transcript_from_file",
    "load_transcript_from_text",
]
