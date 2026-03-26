# Digo the Scribe

**Digo** is a Hyper Agent that listens to Digital Gold Co Google Meet sessions and produces
meticulous, structured meeting notes for members who are unable to attend and for internal
use by Operations Manager Benjamin J. Snider (aka *thewriterben*).

---

## Key capabilities

| Feature | Description |
|---|---|
| **Meeting notes** | Parses Google Meet caption exports (or pasted transcripts) and produces structured, Markdown-formatted notes with speaker attribution. |
| **Battle Plan cross-reference** | Every significant discussion point is matched against the Digital Gold Co Battle Plan PDF, with exact page citations. |
| **Beyond Bitcoin reference** | Key crypto/fund topics are cross-referenced against *Beyond Bitcoin* by John Gotts, with page citations. |
| **Progress reports** | Generates concise reports showing Battle Plan milestone progress and blockers. |
| **Anti-hallucination** | Digo **never fabricates** information. When it cannot confirm a fact from the transcript or loaded documents it flags it `[NEEDS VERIFICATION — see Operations Manager]` and can generate a formal escalation notice to Benjamin Snider. |
| **Extensible resources** | Additional PDFs (e.g. CFV-Metrics-Agent data) can be loaded at any time without code changes. |

---

## Project structure

```
Digo-the-Scribe/
├── src/digo/
│   ├── __init__.py          # Package metadata
│   ├── agent.py             # Core DigoAgent orchestration
│   ├── cli.py               # Command-line interface
│   ├── config.py            # All settings (loaded from env vars)
│   ├── meeting_transcript.py# Google Meet transcript parser
│   ├── pdf_processor.py     # PDF loading & retrieval
│   └── prompts.py           # All LLM prompts (auditable, no logic)
├── tests/
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_meeting_transcript.py
│   └── test_pdf_processor.py
├── resources/               # Place PDF files here (gitignored)
│   └── README.txt
├── output/                  # Generated notes & reports (gitignored)
│   ├── notes/
│   └── reports/
├── config/                  # Google credentials (gitignored)
├── .env.example             # Environment variable template
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

These files are excluded from version control (`.gitignore`) to protect sensitive
business information.

### 4. (Optional) Google credentials

To use Google Workspace APIs (future: auto-fetching Meet transcripts), place your
OAuth2 credentials JSON from the Google Cloud Console at:

```
config/google_credentials.json
```

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

As additional resources become available (website links, CFV-Metrics-Agent data,
updated Battle Plan versions), load them at runtime:

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
