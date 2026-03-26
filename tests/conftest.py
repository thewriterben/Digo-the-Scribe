"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def no_env_api_key(monkeypatch):
    """
    By default, strip the Anthropic key so tests don't accidentally
    call the live API.  Individual tests that need a mock LLM set up
    their own mock.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
