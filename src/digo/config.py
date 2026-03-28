"""
Configuration for Digo the Scribe.

All settings are loaded from environment variables (see .env.example).
No secrets are hard-coded here.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present (development convenience)
load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RESOURCES_DIR = BASE_DIR / "resources"
OUTPUT_DIR = BASE_DIR / "output"
NOTES_DIR = OUTPUT_DIR / "notes"
REPORTS_DIR = OUTPUT_DIR / "reports"

# PDF resources — place files here after receiving them
BATTLE_PLAN_PDF = RESOURCES_DIR / "battle_plan.pdf"
BEYOND_BITCOIN_PDF = RESOURCES_DIR / "beyond_bitcoin.pdf"
DIGITAL_GOLD_WHITE_PAPER_PDF = RESOURCES_DIR / "digital_gold_white_paper.pdf"

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

# Model used for note-taking and analysis.
# Claude is chosen for its strong instruction-following and low hallucination
# rate, which is critical given the financial stakes of this project.
LLM_MODEL: str = os.environ.get("LLM_MODEL", "claude-3-5-sonnet-20241022")

# Maximum tokens returned per LLM call
LLM_MAX_TOKENS: int = int(os.environ.get("LLM_MAX_TOKENS", "4096"))

# Temperature — kept low to discourage fabrication
LLM_TEMPERATURE: float = float(os.environ.get("LLM_TEMPERATURE", "0.0"))

# ---------------------------------------------------------------------------
# Google Meet / Google Workspace
# ---------------------------------------------------------------------------
GOOGLE_CREDENTIALS_FILE: str = os.environ.get(
    "GOOGLE_CREDENTIALS_FILE", str(BASE_DIR / "config" / "google_credentials.json")
)

GOOGLE_TOKEN_FILE: str = os.environ.get(
    "GOOGLE_TOKEN_FILE", str(BASE_DIR / "config" / "token.json")
)

# Google Calendar event ID of the meeting to monitor (optional; used for
# auto-fetching transcripts when available)
MEET_CALENDAR_EVENT_ID: str = os.environ.get("MEET_CALENDAR_EVENT_ID", "")

# ---------------------------------------------------------------------------
# Operations Manager contact
# ---------------------------------------------------------------------------
OPS_MANAGER_NAME: str = "Benjamin J. Snider"
OPS_MANAGER_EMAIL: str = os.environ.get("OPS_MANAGER_EMAIL", "")

# ---------------------------------------------------------------------------
# Anti-hallucination threshold
# ---------------------------------------------------------------------------
# When Digo's self-assessed confidence falls below this value it will
# escalate the item to the Operations Manager instead of stating it as fact.
CONFIDENCE_THRESHOLD: float = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.85"))

# ---------------------------------------------------------------------------
# CFV Metrics Agent integration
# ---------------------------------------------------------------------------
# Base URL for the cfv-metrics-agent REST API.
CFV_METRICS_API_URL: str = os.environ.get("CFV_METRICS_API_URL", "http://localhost:3000")

# Directory for storing CFV data files (snapshots, history, alerts).
CFV_DATA_DIR = OUTPUT_DIR / "cfv_data"

# Percentage deviation threshold above which a price-vs-fair-value alert fires.
CFV_ALERT_THRESHOLD: float = float(os.environ.get("CFV_ALERT_THRESHOLD", "20.0"))

# DGF coins tracked by the cfv-metrics-agent (comma-separated env override).
_cfv_coins_env: str = os.environ.get("CFV_COINS", "BTC,ETH,DASH,NANO,NEAR,ICP,XLM,XRP,ADA,DOT,LINK")
CFV_COINS: list[str] = [c.strip().upper() for c in _cfv_coins_env.split(",") if c.strip()]


def validate() -> list[str]:
    """Return a list of configuration warnings (not errors) for missing items."""
    warnings: list[str] = []
    if not ANTHROPIC_API_KEY:
        warnings.append("ANTHROPIC_API_KEY is not set — LLM calls will fail.")
    if not Path(GOOGLE_CREDENTIALS_FILE).exists():
        warnings.append(
            f"GOOGLE_CREDENTIALS_FILE not found at {GOOGLE_CREDENTIALS_FILE}. "
            "Download your OAuth2 credentials JSON from Google Cloud Console and place it there."
        )
    if not BATTLE_PLAN_PDF.exists():
        warnings.append(
            f"Battle Plan PDF not found at {BATTLE_PLAN_PDF}. Please place it there when available."
        )
    if not BEYOND_BITCOIN_PDF.exists():
        warnings.append(
            f"Beyond Bitcoin PDF not found at {BEYOND_BITCOIN_PDF}. "
            "Please place it there when available."
        )
    if not DIGITAL_GOLD_WHITE_PAPER_PDF.exists():
        warnings.append(
            f"Digital Gold White Paper PDF not found at {DIGITAL_GOLD_WHITE_PAPER_PDF}. "
            "Please place it there when available."
        )
    if not OPS_MANAGER_EMAIL:
        warnings.append("OPS_MANAGER_EMAIL is not set — escalation emails cannot be sent.")
    if not (0.0 <= LLM_TEMPERATURE <= 1.0):
        warnings.append(f"LLM_TEMPERATURE={LLM_TEMPERATURE} is outside the valid range [0.0, 1.0].")
    if not (1 <= LLM_MAX_TOKENS <= 200_000):
        warnings.append(f"LLM_MAX_TOKENS={LLM_MAX_TOKENS} is outside the valid range [1, 200000].")
    if not (0.0 <= CONFIDENCE_THRESHOLD <= 1.0):
        warnings.append(
            f"CONFIDENCE_THRESHOLD={CONFIDENCE_THRESHOLD} is outside the valid range [0.0, 1.0]."
        )
    return warnings
