"""Tests for the CFV API client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from digo.cfv_client import (
    CFVClient,
    CFVCoinMetrics,
    CFVCollectorHealth,
    CFVComponentMetrics,
    CFVPortfolioSnapshot,
    _float_or_none,
)

# ---------------------------------------------------------------------------
# Sample API responses (representative of cfv-metrics-agent output)
# ---------------------------------------------------------------------------

SAMPLE_BTC_RESPONSE = {
    "symbol": "BTC",
    "name": "Bitcoin",
    "metrics": {
        "currentPrice": 65000.0,
        "fairValue": 72000.0,
        "cfvScore": 85.5,
        "valuationStatus": "UNDERVALUED",
        "priceMultiplier": 1.107,
        "confidence": 0.92,
        "communitySize": 9800000.0,
        "annualTxValue": 5200000000.0,
        "annualTxCount": 290000000.0,
        "developers": 1200.0,
    },
}

SAMPLE_ETH_RESPONSE = {
    "symbol": "ETH",
    "name": "Ethereum",
    "metrics": {
        "currentPrice": 3200.0,
        "fairValue": 2800.0,
        "cfvScore": 78.2,
        "valuationStatus": "OVERVALUED",
        "priceMultiplier": 0.875,
        "confidence": 0.88,
        "communitySize": 7200000.0,
        "annualTxValue": 3100000000.0,
        "annualTxCount": 1800000000.0,
        "developers": 4200.0,
    },
}

SAMPLE_RATE_LIMIT_RESPONSE = {
    "status": "healthy",
    "remaining": 95,
    "limit": 100,
}


# ---------------------------------------------------------------------------
# _float_or_none
# ---------------------------------------------------------------------------


class TestFloatOrNone:
    def test_none_returns_none(self):
        assert _float_or_none(None) is None

    def test_int_converts(self):
        assert _float_or_none(42) == 42.0

    def test_float_passes_through(self):
        assert _float_or_none(3.14) == pytest.approx(3.14)

    def test_string_float_converts(self):
        assert _float_or_none("1.5") == pytest.approx(1.5)

    def test_invalid_string_returns_none(self):
        assert _float_or_none("not_a_number") is None

    def test_empty_string_returns_none(self):
        assert _float_or_none("") is None


# ---------------------------------------------------------------------------
# CFVClient — _parse_coin_metrics
# ---------------------------------------------------------------------------


class TestParsesCoinMetrics:
    def _client(self) -> CFVClient:
        return CFVClient(base_url="http://localhost:3000")

    def test_parse_btc(self):
        client = self._client()
        coin = client._parse_coin_metrics(SAMPLE_BTC_RESPONSE)

        assert isinstance(coin, CFVCoinMetrics)
        assert coin.symbol == "BTC"
        assert coin.name == "Bitcoin"
        assert coin.current_price == pytest.approx(65000.0)
        assert coin.fair_value == pytest.approx(72000.0)
        assert coin.cfv_score == pytest.approx(85.5)
        assert coin.valuation_status == "UNDERVALUED"
        assert coin.price_multiplier == pytest.approx(1.107)
        assert coin.confidence_level == pytest.approx(0.92)

    def test_parse_eth_overvalued(self):
        client = self._client()
        coin = client._parse_coin_metrics(SAMPLE_ETH_RESPONSE)

        assert coin.symbol == "ETH"
        assert coin.valuation_status == "OVERVALUED"
        assert coin.price_multiplier == pytest.approx(0.875)

    def test_parse_components(self):
        client = self._client()
        coin = client._parse_coin_metrics(SAMPLE_BTC_RESPONSE)

        assert isinstance(coin.components, CFVComponentMetrics)
        assert coin.components.community_size == pytest.approx(9800000.0)
        assert coin.components.annual_tx_value == pytest.approx(5200000000.0)
        assert coin.components.annual_tx_count == pytest.approx(290000000.0)
        assert coin.components.developers == pytest.approx(1200.0)

    def test_parse_multiplier_computed_when_missing(self):
        """When priceMultiplier is absent, it should be computed from prices."""
        client = self._client()
        data = {
            "symbol": "DASH",
            "name": "Dash",
            "metrics": {
                "currentPrice": 50.0,
                "fairValue": 100.0,
                "cfvScore": 60.0,
                "valuationStatus": "UNDERVALUED",
                "confidence": 0.75,
            },
        }
        coin = client._parse_coin_metrics(data)
        assert coin.price_multiplier == pytest.approx(2.0)  # 100 / 50

    def test_parse_unknown_valuation_status(self):
        client = self._client()
        data = {
            "symbol": "ICP",
            "name": "Internet Computer",
            "metrics": {"currentPrice": 10.0},
        }
        coin = client._parse_coin_metrics(data)
        assert coin.valuation_status == "UNKNOWN"

    def test_parse_snake_case_keys(self):
        """Support snake_case API responses."""
        client = self._client()
        data = {
            "symbol": "NEAR",
            "name": "NEAR Protocol",
            "metrics": {
                "current_price": 5.0,
                "fair_value": 8.0,
                "cfv_score": 70.0,
                "valuation_status": "undervalued",
                "confidence_level": 0.80,
                "community_size": 1000000.0,
            },
        }
        coin = client._parse_coin_metrics(data)
        assert coin.current_price == pytest.approx(5.0)
        assert coin.fair_value == pytest.approx(8.0)
        assert coin.valuation_status == "UNDERVALUED"


# ---------------------------------------------------------------------------
# CFVClient — HTTP layer (mocked)
# ---------------------------------------------------------------------------


def _make_mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    mock_response = MagicMock()
    mock_response.json.return_value = json_data
    mock_response.status_code = status_code
    if status_code >= 400:
        import httpx

        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "HTTP error", request=MagicMock(), response=mock_response
        )
    else:
        mock_response.raise_for_status.return_value = None
    return mock_response


class TestCFVClientFetchCoinMetrics:
    def _client(self) -> CFVClient:
        return CFVClient(base_url="http://localhost:3000")

    def test_fetch_coin_metrics_success(self):
        client = self._client()
        mock_resp = _make_mock_response(SAMPLE_BTC_RESPONSE)

        with patch("digo.cfv_client.httpx.Client") as mock_http:
            mock_http.return_value.__enter__.return_value.get.return_value = mock_resp
            coin = client.fetch_coin_metrics("BTC")

        assert coin is not None
        assert coin.symbol == "BTC"
        assert coin.current_price == pytest.approx(65000.0)

    def test_fetch_coin_metrics_connection_error(self):
        import httpx

        client = self._client()

        with patch("digo.cfv_client.httpx.Client") as mock_http:
            mock_http.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError(
                "connection refused"
            )
            result = client.fetch_coin_metrics("BTC")

        assert result is None

    def test_fetch_coin_metrics_timeout(self):
        import httpx

        client = self._client()

        with patch("digo.cfv_client.httpx.Client") as mock_http:
            mock_http.return_value.__enter__.return_value.get.side_effect = httpx.TimeoutException(
                "timeout"
            )
            result = client.fetch_coin_metrics("BTC")

        assert result is None

    def test_fetch_coin_metrics_http_error(self):
        client = self._client()
        mock_resp = _make_mock_response({}, status_code=404)

        with patch("digo.cfv_client.httpx.Client") as mock_http:
            mock_http.return_value.__enter__.return_value.get.return_value = mock_resp
            result = client.fetch_coin_metrics("UNKNOWN")

        assert result is None

    def test_fetch_coin_metrics_unexpected_error(self):
        client = self._client()

        with patch("digo.cfv_client.httpx.Client") as mock_http:
            mock_http.return_value.__enter__.return_value.get.side_effect = RuntimeError(
                "unexpected"
            )
            result = client.fetch_coin_metrics("BTC")

        assert result is None


class TestCFVClientFetchAllCoins:
    def _client(self) -> CFVClient:
        return CFVClient(base_url="http://localhost:3000")

    def test_fetch_all_coins_returns_snapshot(self):
        client = self._client()

        def _mock_fetch(symbol: str) -> CFVCoinMetrics | None:
            if symbol == "BTC":
                return client._parse_coin_metrics(SAMPLE_BTC_RESPONSE)
            if symbol == "ETH":
                return client._parse_coin_metrics(SAMPLE_ETH_RESPONSE)
            return None

        with (
            patch.object(client, "fetch_coin_metrics", side_effect=_mock_fetch),
            patch("digo.cfv_client.config.CFV_COINS", ["BTC", "ETH", "DASH"]),
        ):
            snapshot = client.fetch_all_coins()

        assert isinstance(snapshot, CFVPortfolioSnapshot)
        assert len(snapshot.coins) == 2  # DASH returned None
        assert {c.symbol for c in snapshot.coins} == {"BTC", "ETH"}

    def test_fetch_all_coins_api_unavailable(self):
        client = self._client()

        with (
            patch.object(client, "fetch_coin_metrics", return_value=None),
            patch("digo.cfv_client.config.CFV_COINS", ["BTC", "ETH"]),
        ):
            snapshot = client.fetch_all_coins()

        assert isinstance(snapshot, CFVPortfolioSnapshot)
        assert snapshot.coins == []

    def test_fetch_all_coins_uses_config_coins(self):
        client = self._client()
        called_with = []

        def _track(symbol):
            called_with.append(symbol)
            return None

        with (
            patch.object(client, "fetch_coin_metrics", side_effect=_track),
            patch("digo.cfv_client.config.CFV_COINS", ["BTC", "ETH", "DASH"]),
        ):
            client.fetch_all_coins()

        assert called_with == ["BTC", "ETH", "DASH"]


class TestCFVClientFetchCollectorHealth:
    def _client(self) -> CFVClient:
        return CFVClient(base_url="http://localhost:3000")

    def test_fetch_health_success(self):
        client = self._client()
        mock_resp = _make_mock_response(SAMPLE_RATE_LIMIT_RESPONSE)

        with patch("digo.cfv_client.httpx.Client") as mock_http:
            mock_http.return_value.__enter__.return_value.get.return_value = mock_resp
            health = client.fetch_collector_health()

        assert isinstance(health, CFVCollectorHealth)
        assert health.status == "healthy"
        assert health.rate_limit_remaining == 95

    def test_fetch_health_unavailable(self):
        import httpx

        client = self._client()

        with patch("digo.cfv_client.httpx.Client") as mock_http:
            mock_http.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError(
                "refused"
            )
            health = client.fetch_collector_health()

        assert health.status == "unavailable"
