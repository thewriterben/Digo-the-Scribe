# Contributing to Digo the Scribe

Thank you for your interest in contributing to Digo! This guide explains how to
set up your environment, run tests, and submit changes.

---

## Prerequisites

- **Python 3.10+**
- **portaudio** system library (required by PyAudio for live listening)
  - Ubuntu/Debian: `sudo apt-get install portaudio19-dev`
  - macOS: `brew install portaudio`
  - Windows: PyAudio wheels are typically prebuilt

---

## Development setup

```bash
git clone https://github.com/thewriterben/Digo-the-Scribe.git
cd Digo-the-Scribe
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

---

## Code style

This project uses **[Ruff](https://docs.astral.sh/ruff/)** for both linting and
formatting.

```bash
# Check for lint errors
ruff check src/ tests/

# Auto-fix what can be fixed
ruff check --fix src/ tests/

# Check formatting
ruff format --check src/ tests/

# Auto-format
ruff format src/ tests/
```

Key rules enforced: `E`, `W`, `F`, `I` (isort), `UP` (pyupgrade), `B`
(bugbear), `SIM` (simplify), `RUF`.

---

## Running tests

```bash
# Full suite with coverage
pytest tests/ -v --cov --cov-report=term-missing

# Run a single test file
pytest tests/test_agent.py -v

# Run a specific test
pytest tests/test_agent.py::TestDigoAgentInit::test_status_returns_string -v
```

The minimum coverage threshold is **80 %** (configured in `pyproject.toml`).

---

## Project layout

| Directory | Purpose |
|---|---|
| `src/digo/` | Main source package |
| `tests/` | Pytest test suite |
| `resources/` | PDF resource files (gitignored) |
| `output/` | Generated notes and reports (gitignored) |
| `config/` | Google OAuth credentials (gitignored) |

---

## Adding a new feature

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Write tests first in `tests/`
3. Implement the feature in `src/digo/`
4. Run `ruff check` + `ruff format` + `pytest`
5. Update `README.md` if the feature is user-facing
6. Open a pull request against `main`

---

## Commit messages

Use clear, descriptive commit messages. Prefix with a category when helpful:

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `test:` — adding or updating tests
- `ci:` — CI/CD changes
- `refactor:` — code change that is neither a fix nor a feature

---

## Reporting issues

Use GitHub Issues. Please include:

- Python version (`python --version`)
- Operating system
- Full error traceback
- Steps to reproduce

For audio-related issues, also include the output of:
```bash
python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"
```

---

## Security

- **Never** commit secrets or API keys.
- Use the `.env` file for local configuration (it is gitignored).
- Report security concerns privately to the Operations Manager.
