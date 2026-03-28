"""Tests for CFV data store."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from digo.cfv_client import CFVCoinMetrics, CFVComponentMetrics, CFVPortfolioSnapshot
from digo.cfv_data_store import CFVDataStore, _coin_to_dict, _dict_to_coin

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_snapshot(coins: list[CFVCoinMetrics] | None = None) -> CFVPortfolioSnapshot:
    if coins is None:
        coins = [
            CFVCoinMetrics(
                symbol="BTC",
                name="Bitcoin",
                current_price=65000.0,
                fair_value=72000.0,
                cfv_score=85.5,
                valuation_status="UNDERVALUED",
                price_multiplier=1.107,
                confidence_level=0.92,
                components=CFVComponentMetrics(
                    community_size=9800000.0,
                    annual_tx_value=5200000000.0,
                    annual_tx_count=290000000.0,
                    developers=1200.0,
                ),
            ),
            CFVCoinMetrics(
                symbol="ETH",
                name="Ethereum",
                current_price=3200.0,
                fair_value=2800.0,
                cfv_score=78.2,
                valuation_status="OVERVALUED",
                price_multiplier=0.875,
                confidence_level=0.88,
                components=CFVComponentMetrics(),
            ),
        ]
    return CFVPortfolioSnapshot(
        coins=coins,
        fetched_at="2026-03-28T08:00:00+00:00",
        api_url="http://localhost:3000",
    )


@pytest.fixture
def store(tmp_path: Path) -> CFVDataStore:
    return CFVDataStore(base_dir=tmp_path / "cfv_data")


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------


class TestSaveSnapshot:
    def test_creates_daily_json_file(self, store: CFVDataStore):
        snapshot = _make_snapshot()
        path = store.save_snapshot(snapshot, date="2026-03-28")

        assert path.exists()
        assert path.name == "2026-03-28.json"

    def test_json_contains_expected_fields(self, store: CFVDataStore):
        snapshot = _make_snapshot()
        path = store.save_snapshot(snapshot, date="2026-03-28")

        data = json.loads(path.read_text())
        assert "coins" in data
        assert "fetched_at" in data
        assert "api_url" in data
        assert len(data["coins"]) == 2

    def test_coin_fields_in_json(self, store: CFVDataStore):
        snapshot = _make_snapshot()
        path = store.save_snapshot(snapshot, date="2026-03-28")

        data = json.loads(path.read_text())
        btc = next(c for c in data["coins"] if c["symbol"] == "BTC")
        assert btc["current_price"] == pytest.approx(65000.0)
        assert btc["fair_value"] == pytest.approx(72000.0)
        assert btc["valuation_status"] == "UNDERVALUED"

    def test_raw_field_excluded(self, store: CFVDataStore):
        """The raw API payload should not be persisted."""
        coin = CFVCoinMetrics(
            symbol="BTC",
            name="Bitcoin",
            current_price=65000.0,
            fair_value=72000.0,
            cfv_score=85.5,
            valuation_status="UNDERVALUED",
            price_multiplier=1.1,
            confidence_level=0.9,
            raw={"someHugePayload": True},
        )
        snapshot = _make_snapshot([coin])
        path = store.save_snapshot(snapshot, date="2026-03-28")

        data = json.loads(path.read_text())
        assert "raw" not in data["coins"][0]


class TestLoadSnapshot:
    def test_round_trip(self, store: CFVDataStore):
        snapshot = _make_snapshot()
        store.save_snapshot(snapshot, date="2026-03-28")
        loaded = store.load_snapshot("2026-03-28")

        assert loaded is not None
        assert len(loaded.coins) == 2
        btc = next(c for c in loaded.coins if c.symbol == "BTC")
        assert btc.current_price == pytest.approx(65000.0)
        assert btc.valuation_status == "UNDERVALUED"

    def test_missing_date_returns_none(self, store: CFVDataStore):
        result = store.load_snapshot("2000-01-01")
        assert result is None

    def test_corrupted_file_returns_none(self, store: CFVDataStore, tmp_path: Path):
        daily_dir = store._daily_dir
        daily_dir.mkdir(parents=True, exist_ok=True)
        (daily_dir / "2026-03-28.json").write_text("NOT JSON", encoding="utf-8")

        result = store.load_snapshot("2026-03-28")
        assert result is None


class TestLoadLatestSnapshot:
    def test_returns_none_when_no_data(self, store: CFVDataStore):
        assert store.load_latest_snapshot() is None

    def test_returns_most_recent(self, store: CFVDataStore):
        snap_old = _make_snapshot()
        snap_new = _make_snapshot()

        store.save_snapshot(snap_old, date="2026-03-27")
        store.save_snapshot(snap_new, date="2026-03-28")

        latest = store.load_latest_snapshot()
        assert latest is not None
        assert latest.fetched_at == snap_new.fetched_at

    def test_list_snapshot_dates_sorted(self, store: CFVDataStore):
        store.save_snapshot(_make_snapshot(), date="2026-03-27")
        store.save_snapshot(_make_snapshot(), date="2026-03-28")
        store.save_snapshot(_make_snapshot(), date="2026-03-26")

        dates = store.list_snapshot_dates()
        assert dates == ["2026-03-26", "2026-03-27", "2026-03-28"]


# ---------------------------------------------------------------------------
# History CSV
# ---------------------------------------------------------------------------


class TestAppendHistory:
    def test_creates_csv_with_headers(self, store: CFVDataStore):
        snapshot = _make_snapshot()
        store.append_history(snapshot, date="2026-03-28")

        assert store._history_file.exists()
        with store._history_file.open() as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) == 2
        assert "symbol" in rows[0]
        assert "current_price" in rows[0]

    def test_appends_on_second_call(self, store: CFVDataStore):
        snapshot = _make_snapshot()
        store.append_history(snapshot, date="2026-03-27")
        store.append_history(snapshot, date="2026-03-28")

        rows = store.load_history()
        assert len(rows) == 4  # 2 coins x 2 days

    def test_header_not_duplicated(self, store: CFVDataStore):
        snapshot = _make_snapshot()
        store.append_history(snapshot, date="2026-03-27")
        store.append_history(snapshot, date="2026-03-28")

        with store._history_file.open() as fh:
            content = fh.read()
        # "date" should appear only once (as header)
        assert content.count("date,") == 1


class TestLoadHistory:
    def test_empty_when_no_file(self, store: CFVDataStore):
        assert store.load_history() == []

    def test_returns_rows(self, store: CFVDataStore):
        snapshot = _make_snapshot()
        store.append_history(snapshot, date="2026-03-28")

        rows = store.load_history()
        assert len(rows) == 2
        assert rows[0]["date"] == "2026-03-28"


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


class TestSaveAlerts:
    def test_creates_alert_json(self, store: CFVDataStore):
        alerts = [
            {
                "symbol": "BTC",
                "name": "Bitcoin",
                "current_price": 65000.0,
                "fair_value": 72000.0,
                "deviation_pct": -9.7,
                "valuation_status": "UNDERVALUED",
            }
        ]
        path = store.save_alerts(alerts, date="2026-03-28")

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["date"] == "2026-03-28"
        assert len(data["alerts"]) == 1

    def test_load_alerts_returns_list(self, store: CFVDataStore):
        alerts = [{"symbol": "ETH", "deviation_pct": 25.0}]
        store.save_alerts(alerts, date="2026-03-28")

        loaded = store.load_alerts("2026-03-28")
        assert len(loaded) == 1
        assert loaded[0]["symbol"] == "ETH"

    def test_load_alerts_missing_date_returns_empty(self, store: CFVDataStore):
        assert store.load_alerts("1999-01-01") == []


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


class TestCoinSerialisationHelpers:
    def test_round_trip(self):
        coin = CFVCoinMetrics(
            symbol="DASH",
            name="Dash",
            current_price=50.0,
            fair_value=100.0,
            cfv_score=60.0,
            valuation_status="UNDERVALUED",
            price_multiplier=2.0,
            confidence_level=0.75,
            components=CFVComponentMetrics(
                community_size=500000.0,
                annual_tx_value=100000000.0,
                annual_tx_count=10000000.0,
                developers=300.0,
            ),
        )
        d = _coin_to_dict(coin)
        restored = _dict_to_coin(d)

        assert restored.symbol == "DASH"
        assert restored.current_price == pytest.approx(50.0)
        assert restored.components.community_size == pytest.approx(500000.0)
