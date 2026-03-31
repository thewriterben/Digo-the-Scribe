# Changelog

All notable changes to Digo the Scribe are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- `format_snapshot_summary()` — public API function for formatting CFV portfolio
  snapshots (previously private `_format_snapshot_summary`)
- URL validation for `CFV_METRICS_API_URL` in `config.validate()`
- Safe parsing of numeric environment variables (`LLM_MAX_TOKENS`,
  `LLM_TEMPERATURE`, `CONFIDENCE_THRESHOLD`, `CFV_ALERT_THRESHOLD`) — invalid
  values now fall back to defaults instead of crashing with ValueError
- Mutual exclusion check in `notes` CLI command — providing both `--transcript`
  and `--text` now produces a clear error instead of silently ignoring one
- Error handling for CFV snapshot file writes (`OSError`) in `cfv_data_store.py`
- 22 new tests: CFV CLI commands, progress reports, env var error handling,
  URL validation, notes mutual exclusion (256 total, 93% coverage)

### Changed
- Moved lazy imports to module level in `cfv_client.py` (datetime),
  `cfv_data_store.py` (CFVComponentMetrics), and `cfv_reporter.py`
  (SYSTEM_PROMPT, config) for better startup reliability and IDE support
- Added type annotations for `DigoAgent._cfv_client` and `._cfv_store` fields
- Added `anthropic.Anthropic | None` type annotation for `CFVReporter.__init__`
  `llm_client` parameter
- Replaced `getattr()` calls with direct attribute access in `cli.py` `cmd_listen`

---

## [0.2.0] — 2026-03-28

### Added
- **CFV Metrics integration** — read-only HTTP client (`cfv_client.py`) for
  the cfv-metrics-agent REST API, with structured dataclasses (`CFVCoinMetrics`,
  `CFVPortfolioSnapshot`, `CFVCollectorHealth`, `CFVComponentMetrics`)
- **CFV data persistence** (`cfv_data_store.py`) — daily JSON snapshots,
  append-only CSV history, and alert records under `output/cfv_data/`
- **CFV report generator** (`cfv_reporter.py`) — daily performance reports,
  Battle Plan cross-reference analysis, and deviation alert checks with
  plain-text fallbacks when the LLM is unavailable
- **CFV CLI commands** — `cfv-report`, `cfv-snapshot`, `cfv-alerts`,
  `cfv-analysis` subcommands in the CLI
- **CFV daily report workflow** (`.github/workflows/cfv-daily-report.yml`) —
  scheduled GitHub Actions workflow that takes daily snapshots, generates
  reports, and creates GitHub Issues when alerts fire
- **CFV prompt templates** — `CFV_DAILY_REPORT_PROMPT_TEMPLATE`,
  `CFV_BATTLE_PLAN_ANALYSIS_PROMPT_TEMPLATE`, and `CFV_ALERT_PROMPT_TEMPLATE`
  in `prompts.py`
- **Live CFV context in meeting notes** — when a transcript mentions CFV or
  fund performance keywords, live data from cfv-metrics-agent is injected
  into the note-taking prompt
- CFV exports in `__init__.py` — `CFVClient`, `CFVCoinMetrics`,
  `CFVPortfolioSnapshot`, `CFVCollectorHealth`, `CFVComponentMetrics`,
  `CFVDataStore`, `CFVReporter` now available via `from digo import …`
- Test suites for CFV modules: `test_cfv_client.py`, `test_cfv_data_store.py`,
  `test_cfv_reporter.py` (100+ new tests)
- `CFV_INTEGRATION.md` — integration guide with setup, CLI usage, data storage
  layout, and sample output
- `.env.example` updated with `CFV_METRICS_API_URL`, `CFV_ALERT_THRESHOLD`,
  `CFV_COINS` variables
- `httpx` added as a dependency for CFV API communication
- Public API exports in `__init__.py` with `__all__` — cleaner imports
  (`from digo import DigoAgent`)
- `--version` flag for the CLI (`digo --version`)
- LLM parameter validation in `config.validate()` (temperature, max_tokens,
  confidence threshold range checks)
- JSON structure validation in transcript parser — malformed JSON now logs a
  warning and returns an empty list instead of crashing
- `CONTRIBUTING.md` with development setup, code style, and PR guidelines
- `CHANGELOG.md` (this file)
- Missing test files: `test_google_auth.py`, `test_config.py`
- Pip caching in CI workflow for faster builds

### Changed
- PDF keyword search now includes 3-letter terms (CFV, DAO, API) — threshold
  lowered from `len > 3` to `len >= 3`
- Audio dependencies (`SpeechRecognition`, `PyAudio`) moved to optional
  `[audio]` extra — users who only process file-based transcripts no longer need
  to install them
- Narrowed exception handling in `agent.py` Meet integration (removed redundant
  `ImportError` from `(ImportError, Exception)` catch)
- LLM calls now include a 120-second timeout to prevent indefinite hangs
- Audio listener sets stop event on microphone access failure for cleaner
  thread cleanup
- Version bumped to 0.2.0

### Removed
- Unused `pydantic` dependency
- Unused `pytest-asyncio` dependency and `asyncio_mode` config

### Fixed
- CI workflow: added `portaudio19-dev` system dependency so PyAudio builds
  successfully on GitHub Actions runners
- README: added missing test files to project structure listing
- README: updated Google credentials section (feature is implemented, not
  "future")

---

## [0.1.0] — 2026-03-15

### Added
- Initial release
- `DigoAgent` — core orchestration engine for meeting notes
- CLI with `status`, `notes`, `report`, `escalate`, `load-resource`, `listen`
  commands
- Live meeting listening via microphone with real-time transcription
- Google Meet session auto-discovery via Google Calendar API
- PDF loading and keyword-based retrieval for Battle Plan, Beyond Bitcoin,
  and Digital Gold White Paper
- Anti-hallucination policy: zero fabrication, cited sources, uncertainty flags,
  escalation notices, temperature 0.0
- Comprehensive test suite (134 tests, 90% coverage)
- CI/CD workflow with Ruff linting and pytest
