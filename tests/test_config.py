"""Tests for digo.config — configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from digo import config


class TestConfigValues:
    """Verify configuration defaults and types."""

    def test_base_dir_is_a_directory(self):
        assert isinstance(config.BASE_DIR, Path)
        assert config.BASE_DIR.is_dir()

    def test_resources_dir_under_base(self):
        assert config.RESOURCES_DIR == config.BASE_DIR / "resources"

    def test_output_dirs_under_base(self):
        assert config.NOTES_DIR == config.OUTPUT_DIR / "notes"
        assert config.REPORTS_DIR == config.OUTPUT_DIR / "reports"

    def test_pdf_paths_are_paths(self):
        assert isinstance(config.BATTLE_PLAN_PDF, Path)
        assert isinstance(config.BEYOND_BITCOIN_PDF, Path)
        assert isinstance(config.DIGITAL_GOLD_WHITE_PAPER_PDF, Path)

    def test_llm_defaults(self):
        assert config.LLM_MODEL == "claude-3-5-sonnet-20241022"
        assert config.LLM_MAX_TOKENS == 4096
        assert config.LLM_TEMPERATURE == 0.0

    def test_confidence_threshold_in_range(self):
        assert 0.0 <= config.CONFIDENCE_THRESHOLD <= 1.0

    def test_ops_manager_name(self):
        assert config.OPS_MANAGER_NAME == "Benjamin J. Snider"


class TestValidate:
    """Tests for config.validate() warning generation."""

    def test_validate_returns_list(self):
        result = config.validate()
        assert isinstance(result, list)

    def test_validate_warns_missing_api_key(self):
        """Should always warn in tests since conftest strips the key."""
        warnings = config.validate()
        assert any("ANTHROPIC_API_KEY" in w for w in warnings)

    def test_validate_warns_missing_pdfs(self):
        """With nonexistent PDF paths, validation should warn."""
        with (
            patch.object(config, "BATTLE_PLAN_PDF", Path("/nonexistent/bp.pdf")),
            patch.object(config, "BEYOND_BITCOIN_PDF", Path("/nonexistent/bb.pdf")),
            patch.object(config, "DIGITAL_GOLD_WHITE_PAPER_PDF", Path("/nonexistent/dg.pdf")),
        ):
            warnings = config.validate()
            assert any("Battle Plan" in w for w in warnings)
            assert any("Beyond Bitcoin" in w for w in warnings)
            assert any("White Paper" in w for w in warnings)

    def test_validate_warns_missing_credentials(self):
        """Should warn when Google credentials file doesn't exist."""
        with patch.object(config, "GOOGLE_CREDENTIALS_FILE", "/nonexistent/creds.json"):
            warnings = config.validate()
            assert any("GOOGLE_CREDENTIALS_FILE" in w for w in warnings)

    def test_validate_warns_missing_ops_email(self):
        """Should warn when OPS_MANAGER_EMAIL is empty."""
        with patch.object(config, "OPS_MANAGER_EMAIL", ""):
            warnings = config.validate()
            assert any("OPS_MANAGER_EMAIL" in w for w in warnings)

    def test_validate_warns_invalid_temperature(self):
        """Should warn when LLM_TEMPERATURE is outside [0.0, 1.0]."""
        with patch.object(config, "LLM_TEMPERATURE", 2.0):
            warnings = config.validate()
            assert any("LLM_TEMPERATURE" in w for w in warnings)

    def test_validate_warns_invalid_max_tokens(self):
        """Should warn when LLM_MAX_TOKENS is outside valid range."""
        with patch.object(config, "LLM_MAX_TOKENS", 0):
            warnings = config.validate()
            assert any("LLM_MAX_TOKENS" in w for w in warnings)

    def test_validate_warns_invalid_confidence_threshold(self):
        """Should warn when CONFIDENCE_THRESHOLD is outside [0.0, 1.0]."""
        with patch.object(config, "CONFIDENCE_THRESHOLD", 1.5):
            warnings = config.validate()
            assert any("CONFIDENCE_THRESHOLD" in w for w in warnings)

    def test_validate_no_warning_for_valid_params(self):
        """Valid LLM params should not produce warnings about them."""
        warnings = config.validate()
        assert not any("LLM_TEMPERATURE" in w for w in warnings)
        assert not any("LLM_MAX_TOKENS" in w for w in warnings)
        assert not any("CONFIDENCE_THRESHOLD" in w for w in warnings)

    def test_validate_warns_invalid_cfv_url(self):
        """Should warn when CFV_METRICS_API_URL is not a valid URL."""
        with patch.object(config, "CFV_METRICS_API_URL", "not-a-url"):
            warnings = config.validate()
            assert any("CFV_METRICS_API_URL" in w for w in warnings)

    def test_validate_no_warning_for_valid_cfv_url(self):
        """Valid CFV URL should not produce a warning."""
        with patch.object(config, "CFV_METRICS_API_URL", "http://localhost:3000"):
            warnings = config.validate()
            assert not any("CFV_METRICS_API_URL" in w for w in warnings)


class TestConfigEnvVarParsing:
    """Tests for safe int/float environment variable parsing."""

    def test_invalid_max_tokens_falls_back(self):
        """Invalid LLM_MAX_TOKENS value should fall back to default."""
        import importlib

        with patch.dict("os.environ", {"LLM_MAX_TOKENS": "not_a_number"}):
            importlib.reload(config)
            assert config.LLM_MAX_TOKENS == 4096
        # Reload with clean env to restore defaults
        importlib.reload(config)

    def test_invalid_temperature_falls_back(self):
        """Invalid LLM_TEMPERATURE value should fall back to default."""
        import importlib

        with patch.dict("os.environ", {"LLM_TEMPERATURE": "hot"}):
            importlib.reload(config)
            assert config.LLM_TEMPERATURE == 0.0
        importlib.reload(config)

    def test_invalid_confidence_threshold_falls_back(self):
        """Invalid CONFIDENCE_THRESHOLD value should fall back to default."""
        import importlib

        with patch.dict("os.environ", {"CONFIDENCE_THRESHOLD": "abc"}):
            importlib.reload(config)
            assert config.CONFIDENCE_THRESHOLD == 0.85
        importlib.reload(config)

    def test_invalid_cfv_alert_threshold_falls_back(self):
        """Invalid CFV_ALERT_THRESHOLD value should fall back to default."""
        import importlib

        with patch.dict("os.environ", {"CFV_ALERT_THRESHOLD": "xyz"}):
            importlib.reload(config)
            assert config.CFV_ALERT_THRESHOLD == 20.0
        importlib.reload(config)
