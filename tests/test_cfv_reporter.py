"""Tests for CFV performance report generator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from digo.cfv_client import CFVCoinMetrics, CFVComponentMetrics, CFVPortfolioSnapshot
from digo.cfv_data_store import CFVDataStore
from digo.cfv_reporter import (
    CFVReporter,
    _compute_alerts,
    _format_alerts_summary,
    _format_snapshot_summary,
    _format_trend_summary,
    _pct_change,
    _plain_alert_report,
    _plain_battle_plan_analysis,
    _plain_daily_report,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_coin(
    symbol: str = "BTC",
    name: str = "Bitcoin",
    current_price: float = 65000.0,
    fair_value: float = 72000.0,
    valuation_status: str = "UNDERVALUED",
    price_multiplier: float = 1.107,
) -> CFVCoinMetrics:
    return CFVCoinMetrics(
        symbol=symbol,
        name=name,
        current_price=current_price,
        fair_value=fair_value,
        cfv_score=85.0,
        valuation_status=valuation_status,
        price_multiplier=price_multiplier,
        confidence_level=0.9,
        components=CFVComponentMetrics(
            community_size=9800000.0,
            annual_tx_value=5200000000.0,
            annual_tx_count=290000000.0,
            developers=1200.0,
        ),
    )


def _make_snapshot(*coins: CFVCoinMetrics) -> CFVPortfolioSnapshot:
    return CFVPortfolioSnapshot(
        coins=list(coins) if coins else [_make_coin()],
        fetched_at="2026-03-28T08:00:00+00:00",
        api_url="http://localhost:3000",
    )


def _make_reporter(
    tmp_path: Path,
    llm_client=None,
    snapshot_to_return: CFVPortfolioSnapshot | None = None,
) -> CFVReporter:
    store = CFVDataStore(base_dir=tmp_path / "cfv_data")
    mock_client = MagicMock()
    if snapshot_to_return is None:
        snapshot_to_return = _make_snapshot()
    mock_client.fetch_all_coins.return_value = snapshot_to_return
    mock_client.fetch_coin_metrics.return_value = (
        snapshot_to_return.coins[0] if snapshot_to_return.coins else None
    )
    return CFVReporter(llm_client=llm_client, cfv_client=mock_client, data_store=store)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestPctChange:
    def test_increase(self):
        assert _pct_change(100.0, 110.0) == pytest.approx(10.0)

    def test_decrease(self):
        assert _pct_change(100.0, 90.0) == pytest.approx(-10.0)

    def test_zero_old_returns_none(self):
        assert _pct_change(0.0, 100.0) is None

    def test_none_returns_none(self):
        assert _pct_change(None, 100.0) is None
        assert _pct_change(100.0, None) is None


class TestComputeAlerts:
    def test_no_alerts_within_threshold(self):
        coin = _make_coin(current_price=65000.0, fair_value=70000.0)  # ~7% deviation
        alerts = _compute_alerts([coin], threshold=20.0)
        assert alerts == []

    def test_alert_triggered_when_deviation_exceeds_threshold(self):
        # 30% below fair value
        coin = _make_coin(current_price=50000.0, fair_value=72000.0)
        alerts = _compute_alerts([coin], threshold=20.0)
        assert len(alerts) == 1
        assert alerts[0]["symbol"] == "BTC"
        assert alerts[0]["deviation_pct"] < -20.0

    def test_overvalued_alert(self):
        # 30% above fair value
        coin = _make_coin(current_price=93600.0, fair_value=72000.0)
        alerts = _compute_alerts([coin], threshold=20.0)
        assert len(alerts) == 1
        assert alerts[0]["deviation_pct"] > 20.0

    def test_missing_prices_skipped(self):
        coin = CFVCoinMetrics(
            symbol="NANO",
            name="Nano",
            current_price=None,
            fair_value=None,
            cfv_score=None,
            valuation_status="UNKNOWN",
            price_multiplier=None,
            confidence_level=None,
        )
        alerts = _compute_alerts([coin], threshold=20.0)
        assert alerts == []

    def test_zero_fair_value_skipped(self):
        coin = _make_coin(current_price=50.0, fair_value=0.0)
        alerts = _compute_alerts([coin], threshold=20.0)
        assert alerts == []


class TestFormatSnapshotSummary:
    def test_contains_symbol(self):
        snapshot = _make_snapshot()
        summary = _format_snapshot_summary(snapshot)
        assert "BTC" in summary

    def test_contains_valuation_status(self):
        snapshot = _make_snapshot()
        summary = _format_snapshot_summary(snapshot)
        assert "UNDERVALUED" in summary

    def test_na_for_none_prices(self):
        coin = CFVCoinMetrics(
            symbol="NANO",
            name="Nano",
            current_price=None,
            fair_value=None,
            cfv_score=None,
            valuation_status="UNKNOWN",
            price_multiplier=None,
            confidence_level=None,
        )
        snapshot = _make_snapshot(coin)
        summary = _format_snapshot_summary(snapshot)
        assert "N/A" in summary


class TestFormatTrendSummary:
    def test_no_previous_snapshot(self):
        current = _make_snapshot()
        result = _format_trend_summary(current, None)
        assert "No previous snapshot" in result

    def test_shows_price_change(self):
        old_coin = _make_coin(current_price=60000.0)
        new_coin = _make_coin(current_price=65000.0)
        old_snap = _make_snapshot(old_coin)
        new_snap = _make_snapshot(new_coin)

        result = _format_trend_summary(new_snap, old_snap)
        assert "BTC" in result
        # 65000 / 60000 - 1 = +8.33%
        assert "+8.33%" in result

    def test_no_matching_coins(self):
        old_snap = _make_snapshot(_make_coin(symbol="ETH"))
        new_snap = _make_snapshot(_make_coin(symbol="BTC"))
        result = _format_trend_summary(new_snap, old_snap)
        assert "No comparable coins" in result


class TestFormatAlertsSummary:
    def test_formats_alerts(self):
        alerts = [
            {
                "symbol": "BTC",
                "name": "Bitcoin",
                "current_price": 50000.0,
                "fair_value": 72000.0,
                "deviation_pct": -30.6,
                "valuation_status": "UNDERVALUED",
            }
        ]
        summary = _format_alerts_summary(alerts)
        assert "BTC" in summary
        assert "-30.6%" in summary


# ---------------------------------------------------------------------------
# Plain-text fallbacks
# ---------------------------------------------------------------------------


class TestPlainFallbacks:
    def test_plain_daily_report_contains_date(self):
        snapshot = _make_snapshot()
        report = _plain_daily_report(snapshot, "2026-03-28")
        assert "2026-03-28" in report
        assert "BTC" in report

    def test_plain_battle_plan_analysis_needs_verification(self):
        snapshot = _make_snapshot()
        report = _plain_battle_plan_analysis(snapshot, "2026-03-28")
        assert "NEEDS VERIFICATION" in report

    def test_plain_alert_report_contains_alert_info(self):
        alerts = [
            {
                "symbol": "ETH",
                "name": "Ethereum",
                "current_price": 5000.0,
                "fair_value": 2800.0,
                "deviation_pct": 78.6,
                "valuation_status": "OVERVALUED",
            }
        ]
        report = _plain_alert_report(alerts, "2026-03-28", threshold=20.0)
        assert "1 deviation alert" in report
        assert "ETH" in report


# ---------------------------------------------------------------------------
# CFVReporter — fetch_and_store_snapshot
# ---------------------------------------------------------------------------


class TestFetchAndStoreSnapshot:
    def test_returns_snapshot(self, tmp_path: Path):
        reporter = _make_reporter(tmp_path)
        snapshot = reporter.fetch_and_store_snapshot()
        assert isinstance(snapshot, CFVPortfolioSnapshot)
        assert len(snapshot.coins) > 0

    def test_stores_daily_json(self, tmp_path: Path):
        reporter = _make_reporter(tmp_path)
        reporter.fetch_and_store_snapshot()

        daily_dir = tmp_path / "cfv_data" / "daily"
        assert daily_dir.exists()
        json_files = list(daily_dir.glob("*.json"))
        assert len(json_files) == 1

    def test_no_coins_not_stored(self, tmp_path: Path):
        empty_snapshot = CFVPortfolioSnapshot(
            coins=[], fetched_at="2026-03-28T08:00:00+00:00", api_url="http://localhost:3000"
        )
        reporter = _make_reporter(tmp_path, snapshot_to_return=empty_snapshot)
        reporter.fetch_and_store_snapshot()

        daily_dir = tmp_path / "cfv_data" / "daily"
        assert not daily_dir.exists() or not list(daily_dir.glob("*.json"))


# ---------------------------------------------------------------------------
# CFVReporter — generate_daily_report
# ---------------------------------------------------------------------------


class TestGenerateDailyReport:
    def test_returns_markdown_string(self, tmp_path: Path):
        reporter = _make_reporter(tmp_path)
        report = reporter.generate_daily_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_unavailable_notice_when_no_coins(self, tmp_path: Path):
        empty_snapshot = CFVPortfolioSnapshot(
            coins=[], fetched_at="2026-03-28T08:00:00+00:00", api_url="http://localhost:3000"
        )
        reporter = _make_reporter(tmp_path, snapshot_to_return=empty_snapshot)
        report = reporter.generate_daily_report(snapshot=empty_snapshot)
        assert "Data Unavailable" in report

    def test_uses_provided_snapshot(self, tmp_path: Path):
        reporter = _make_reporter(tmp_path)
        snapshot = _make_snapshot(_make_coin(symbol="DASH"))
        report = reporter.generate_daily_report(snapshot=snapshot)
        # Should not call fetch_all_coins when snapshot is provided
        reporter._client.fetch_all_coins.assert_not_called()
        assert isinstance(report, str)

    def test_with_mock_llm(self, tmp_path: Path):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "## CFV Daily Report\n\nAll coins healthy."
        mock_response.content = [mock_block]

        mock_llm = MagicMock()
        mock_llm.messages.create.return_value = mock_response

        reporter = _make_reporter(tmp_path, llm_client=mock_llm)
        report = reporter.generate_daily_report()

        mock_llm.messages.create.assert_called_once()
        assert "CFV Daily Report" in report


# ---------------------------------------------------------------------------
# CFVReporter — check_alerts
# ---------------------------------------------------------------------------


class TestCheckAlerts:
    def test_no_alerts_when_within_threshold(self, tmp_path: Path):
        # 7% below fair value — within default 20% threshold
        coin = _make_coin(current_price=67000.0, fair_value=72000.0)
        snapshot = _make_snapshot(coin)
        reporter = _make_reporter(tmp_path, snapshot_to_return=snapshot)

        alerts, report = reporter.check_alerts(snapshot=snapshot, threshold=20.0)

        assert alerts == []
        assert "No significant deviations" in report

    def test_alert_when_exceeds_threshold(self, tmp_path: Path):
        # 30% below fair value
        coin = _make_coin(current_price=50000.0, fair_value=72000.0)
        snapshot = _make_snapshot(coin)
        reporter = _make_reporter(tmp_path, snapshot_to_return=snapshot)

        alerts, _report = reporter.check_alerts(snapshot=snapshot, threshold=20.0)

        assert len(alerts) == 1
        assert alerts[0]["symbol"] == "BTC"

    def test_alerts_saved_to_store(self, tmp_path: Path):
        coin = _make_coin(current_price=50000.0, fair_value=72000.0)
        snapshot = _make_snapshot(coin)
        reporter = _make_reporter(tmp_path, snapshot_to_return=snapshot)

        reporter.check_alerts(snapshot=snapshot, threshold=20.0)

        alerts_dir = tmp_path / "cfv_data" / "alerts"
        assert alerts_dir.exists()
        assert len(list(alerts_dir.glob("*.json"))) == 1

    def test_no_alerts_not_saved(self, tmp_path: Path):
        coin = _make_coin(current_price=67000.0, fair_value=72000.0)
        snapshot = _make_snapshot(coin)
        reporter = _make_reporter(tmp_path, snapshot_to_return=snapshot)

        reporter.check_alerts(snapshot=snapshot, threshold=20.0)

        alerts_dir = tmp_path / "cfv_data" / "alerts"
        assert not alerts_dir.exists() or not list(alerts_dir.glob("*.json"))


# ---------------------------------------------------------------------------
# CFVReporter — generate_battle_plan_analysis
# ---------------------------------------------------------------------------


class TestGenerateBattleplanAnalysis:
    def test_returns_string(self, tmp_path: Path):
        reporter = _make_reporter(tmp_path)
        report = reporter.generate_battle_plan_analysis()
        assert isinstance(report, str)

    def test_unavailable_notice_when_no_coins(self, tmp_path: Path):
        empty_snapshot = CFVPortfolioSnapshot(
            coins=[], fetched_at="2026-03-28T08:00:00+00:00", api_url="http://localhost:3000"
        )
        reporter = _make_reporter(tmp_path, snapshot_to_return=empty_snapshot)
        report = reporter.generate_battle_plan_analysis(snapshot=empty_snapshot)
        assert "Data Unavailable" in report

    def test_missing_battle_plan_noted(self, tmp_path: Path):
        reporter = _make_reporter(tmp_path)
        report = reporter.generate_battle_plan_analysis(battle_plan_excerpts="")
        # Should note that Battle Plan is not loaded
        assert "Battle Plan" in report
