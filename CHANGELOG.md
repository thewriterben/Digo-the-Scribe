# Changelog

All notable changes to Digo the Scribe are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.2.0] — 2026-03-28

### Added
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
