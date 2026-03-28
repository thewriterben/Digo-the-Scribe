# Digo the Scribe

**Digo** is a Hyper Agent that listens to Digital Gold Co Google Meet sessions and produces
meticulous, structured meeting notes for members who are unable to attend and for internal
use by Operations Manager Benjamin J. Snider (aka *thewriterben*).

---

## Key capabilities

| Feature | Description |
|---|---|
| **Live meeting listening** | Listens to a live meeting via microphone, transcribes speech to text in real-time, and produces structured notes when the session ends. |
| **Meeting notes** | Parses Google Meet caption exports (or pasted transcripts) and produces structured, Markdown-formatted notes with speaker attribution. |
| **Battle Plan cross-reference** | Every significant discussion point is matched against the Digital Gold Co Battle Plan PDF, with exact page citations. |
| **Beyond Bitcoin reference** | Key crypto/fund topics are cross-referenced against *Beyond Bitcoin* by John Gotts, with page citations. |
| **Digital Gold White Paper reference** | Topics are cross-referenced against the Digital Gold White Paper, with page citations. |
| **CFV Metrics integration** | Integrates with [cfv-metrics-agent](https://github.com/thewriterben/cfv-metrics-agent) to track Crypto Fair Value performance for all 11 DGF coins, generate daily reports, and fire alerts when price deviates from CFV fair value. |
| **Progress reports** | Generates concise reports showing Battle Plan milestone progress and blockers. |
| **Anti-hallucination** | Digo **never fabricates** information. When it cannot confirm a fact from the transcript or loaded documents it flags it `[NEEDS VERIFICATION — see Operations Manager]` and can generate a formal escalation notice to Benjamin Snider. |
| **Extensible resources** | Additional PDFs can be loaded at any time without code changes. |

---

## Project structure

```
Digo-the-Scribe/
├── src/digo/
│   ├── __init__.py          # Package metadata
│   ├── agent.py             # Core DigoAgent orchestration
│   ├── audio_listener.py    # Live microphone capture & speech-to-text
│   ├── cfv_client.py        # CFV Metrics Agent REST API client
│   ├── cfv_data_store.py    # CFV data persistence (JSON snapshots, CSV history, alerts)
│   ├── cfv_reporter.py      # CFV performance report & alert generator
│   ├── cli.py               # Command-line interface
│   ├── config.py            # All settings (loaded from env vars)
│   ├── google_auth.py       # Google OAuth2 helper
│   ├── google_meet.py       # Google Meet session discovery via Calendar API
│   ├── meeting_transcript.py# Google Meet transcript parser
│   ├── pdf_processor.py     # PDF loading & retrieval
│   └── prompts.py           # All LLM prompts (auditable, no logic)
├── tests/
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_audio_listener.py
│   ├── test_cfv_client.py
│   ├── test_cfv_data_store.py
│   ├── test_cfv_reporter.py
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_google_auth.py
│   ├── test_google_meet.py
│   ├── test_meeting_transcript.py
│   └── test_pdf_processor.py
├── resources/               # Place PDF files here (gitignored)
│   └── README.txt
├── output/                  # Generated notes, reports & CFV data (gitignored)
│   ├── notes/
│   ├── reports/
│   └── cfv_data/
│       ├── daily/           # YYYY-MM-DD.json snapshots
│       ├── history.csv      # Append-only per-coin history
│       └── alerts/          # YYYY-MM-DD_alerts.json
├── .github/
│   └── workflows/
│       ├── ci.yml           # Lint + test on every push/PR
│       └── cfv-daily-report.yml  # Daily CFV performance report (08:00 UTC)
├── .env.example             # Environment variable template
├── CFV_INTEGRATION.md       # CFV integration guide
├── pyproject.toml
└── README.md
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/thewriterben/Digo-the-Scribe.git
cd Digo-the-Scribe
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in:
#   ANTHROPIC_API_KEY=...
#   OPS_MANAGER_EMAIL=...  (Benjamin Snider's email for escalations)
```

### 3. Add resource PDFs

Place the following files in the `resources/` directory:

| File | Description |
|---|---|
| `resources/battle_plan.pdf` | Digital Gold Co Battle Plan |
| `resources/beyond_bitcoin.pdf` | *Beyond Bitcoin* by John Gotts |
| `resources/digital_gold_white_paper.pdf` | Digital Gold White Paper |

These files are excluded from version control (`.gitignore`) to protect sensitive
business information.

### 4. (Optional) Google credentials

To use Google Meet integration (auto-discovering upcoming meetings, fetching
meeting metadata and participants from Google Calendar), place your OAuth2
credentials JSON from the Google Cloud Console at:

```
config/google_credentials.json
```

Run `python -m digo.google_auth` once to complete the browser-based OAuth flow
and cache a token for subsequent runs.

---

## Usage

### Check status

```bash
digo status
```

### Take notes from a transcript file

Google Meet caption exports (`.txt`) and simple `Speaker: text` formats are both supported.

```bash
digo notes \
  --transcript /path/to/transcript.txt \
  --title "Q1 Strategy Review" \
  --date 2026-03-26
```

### Take notes from pasted text

```bash
digo notes \
  --text "Benjamin Snider: Let's discuss milestone 3.
Alice: We're on track for the token launch." \
  --title "Quick Sync" \
  --date 2026-03-26
```

### Listen to a live meeting

Digo can listen to a live meeting through your microphone and transcribe speech in
real-time. When you stop listening (Ctrl+C), it automatically processes the transcript
into structured notes.

```bash
digo listen --title "Q1 Strategy Review" --date 2026-03-26
```

#### Listen with Google Meet integration

Use `--meet` to auto-discover the next upcoming Google Meet session from your Google
Calendar. Digo will fetch the meeting title, date, and participants automatically:

```bash
digo listen --meet
```

You can also specify a particular Google Calendar event ID:

```bash
digo listen --event-id "abc123def456"
```

Combine `--meet` with `--title` or `--date` to override the auto-detected values:

```bash
digo listen --meet --title "Custom Title"
```

> **Note:** Google Meet integration requires valid Google OAuth2 credentials.
> See the [Google credentials](#4-optional-google-credentials) section below.

> **Note:** Live listening requires a working microphone and the audio extras.
> Install them with `pip install -e ".[audio]"` (or `pip install -e ".[dev]"`).
> On Ubuntu/Debian: `sudo apt-get install portaudio19-dev` before `pip install PyAudio`.
> On macOS: `brew install portaudio` before `pip install PyAudio`.

### Generate a progress report

```bash
digo report --notes output/notes/2026-03-26_q1_strategy_review.md
```

### Create an escalation notice

Use this when a topic cannot be confirmed from available documents:

```bash
digo escalate \
  --topic "CFV token price floor mechanism" \
  --context "Discussed during the funding round section of the meeting." \
  --reason "Not found in Battle Plan pages reviewed." \
  --title "Q1 Strategy Review" \
  --date 2026-03-26
```

### Load an additional resource

```bash
digo load-resource --name "CFV Metrics" --path resources/cfv_metrics.pdf
```

---

## CFV Metrics Integration

Digo integrates with [cfv-metrics-agent](https://github.com/thewriterben/cfv-metrics-agent)
to track Crypto Fair Value (CFV) performance for all 11 DGF coins.

### Take a CFV snapshot

```bash
digo cfv-snapshot
```

### Generate a daily CFV performance report

```bash
digo cfv-report
```

### Check for CFV performance alerts

```bash
digo cfv-alerts
```

### Generate a Battle Plan vs CFV analysis

```bash
digo cfv-analysis
```

> See [CFV_INTEGRATION.md](CFV_INTEGRATION.md) for full setup instructions,
> configuration, and sample output.

---

## Running the tests

```bash
pytest tests/ -v
```

---

## Anti-hallucination policy

Digo operates under a strict anti-hallucination policy because inaccuracies could
endanger significant investment decisions:

1. **Zero fabrication** — Digo will never invent facts, statistics, or document
   content.
2. **Cited sources** — Every claim drawn from a reference document includes the
   document name and exact page number.
3. **Uncertainty flags** — Any item that cannot be fully confirmed is marked
   `[NEEDS VERIFICATION — see Operations Manager]`.
4. **Escalation** — Digo can generate a formal escalation notice addressed to
   Operations Manager Benjamin J. Snider for human review.
5. **Low temperature** — The LLM is run at temperature `0.0` (most deterministic)
   to minimise creative drift.

---

## Adding future resources

As additional resources become available (website links, updated Battle Plan versions),
load them at runtime:

```python
from pathlib import Path
from digo.agent import DigoAgent

agent = DigoAgent()
agent.load_resources()                               # loads standard PDFs
agent.load_resource_from_path("CFV Metrics", Path("resources/cfv_metrics.pdf"))
```

Or via the `digo load-resource` CLI command:

```bash
digo load-resource --name "CFV Metrics" --path resources/cfv_metrics.pdf
```

---

## License

Private — Digital Gold Co internal use only.
