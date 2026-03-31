"""
CFV Metrics API client.

Read-only HTTP client for the cfv-metrics-agent REST API.  The cfv-metrics-agent
calculates Crypto Fair Value (CFV) using the 70/10/10/10 formula:

  Community Size (70%) + Annual Transaction Value (10%) +
  Annual Transaction Count (10%) + Developers (10%)

Connection errors are handled gracefully — the cfv-metrics-agent may not always
be running.  All data is returned as structured dataclasses and NEVER fabricated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from digo import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data-classes
# ---------------------------------------------------------------------------


@dataclass
class CFVComponentMetrics:
    """The four weighted components of the CFV formula (70/10/10/10)."""

    community_size: float | None = None
    annual_tx_value: float | None = None
    annual_tx_count: float | None = None
    developers: float | None = None


@dataclass
class CFVCoinMetrics:
    """CFV calculation result for a single DGF coin."""

    symbol: str
    name: str
    current_price: float | None
    fair_value: float | None
    cfv_score: float | None
    valuation_status: str  # "UNDERVALUED" | "OVERVALUED" | "FAIR" | "UNKNOWN"
    price_multiplier: float | None  # fair_value / current_price
    confidence_level: float | None
    components: CFVComponentMetrics = field(default_factory=CFVComponentMetrics)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CFVPortfolioSnapshot:
    """Snapshot of CFV metrics for all tracked DGF coins."""

    coins: list[CFVCoinMetrics] = field(default_factory=list)
    fetched_at: str = ""
    api_url: str = ""


@dataclass
class CFVCollectorHealth:
    """Health/status of the cfv-metrics-agent collector."""

    status: str = "unknown"
    rate_limit_remaining: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class CFVClient:
    """
    Read-only HTTP client for the cfv-metrics-agent REST API.

    Usage::

        client = CFVClient()
        snapshot = client.fetch_all_coins()
        health = client.fetch_collector_health()
    """

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self._base_url = (base_url or config.CFV_METRICS_API_URL).rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_coin_metrics(self, symbol: str) -> CFVCoinMetrics | None:
        """
        Fetch CFV metrics for a single coin.

        Returns ``None`` if the cfv-metrics-agent is unavailable or the coin
        is not supported.
        """
        url = f"{self._base_url}/api/metrics/{symbol.upper()}"
        data = self._get_json(url)
        if data is None:
            return None
        return self._parse_coin_metrics(data)

    def fetch_all_coins(self) -> CFVPortfolioSnapshot:
        """
        Fetch CFV metrics for all configured DGF coins.

        Returns a :class:`CFVPortfolioSnapshot` whose ``coins`` list may be
        empty if the agent is unavailable.
        """
        snapshot = CFVPortfolioSnapshot(
            fetched_at=datetime.now(tz=UTC).isoformat(),
            api_url=self._base_url,
        )
        for symbol in config.CFV_COINS:
            metrics = self.fetch_coin_metrics(symbol)
            if metrics is not None:
                snapshot.coins.append(metrics)
            else:
                logger.warning("Could not fetch CFV metrics for %s", symbol)
        return snapshot

    def fetch_collector_health(self) -> CFVCollectorHealth:
        """
        Fetch the rate-limit / collector health status.

        Returns a :class:`CFVCollectorHealth` with ``status="unavailable"`` if
        the cfv-metrics-agent is not reachable.
        """
        url = f"{self._base_url}/api/rate-limits/status"
        data = self._get_json(url)
        if data is None:
            return CFVCollectorHealth(status="unavailable")

        return CFVCollectorHealth(
            status=data.get("status", "unknown"),
            rate_limit_remaining=data.get("remaining"),
            details=data,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_json(self, url: str) -> dict[str, Any] | None:
        """
        Perform a GET request and return parsed JSON, or ``None`` on error.

        All HTTP/network errors are logged as warnings so callers can degrade
        gracefully rather than crashing.
        """
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError:
            logger.warning(
                "CFV Metrics Agent is not reachable at %s. Ensure cfv-metrics-agent is running.",
                self._base_url,
            )
        except httpx.TimeoutException:
            logger.warning("CFV Metrics Agent request timed out: %s", url)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "CFV Metrics Agent returned HTTP %s for %s",
                exc.response.status_code,
                url,
            )
        except Exception as exc:
            logger.warning("Unexpected error fetching CFV data from %s: %s", url, exc)
        return None

    def _parse_coin_metrics(self, data: dict[str, Any]) -> CFVCoinMetrics:
        """Parse a raw API response dict into a :class:`CFVCoinMetrics`."""
        # The cfv-metrics-agent may nest data under different keys depending on
        # the API version — handle both flat and nested structures defensively.
        metrics_data = data.get("metrics", data)

        current_price = _float_or_none(
            metrics_data.get("currentPrice") or metrics_data.get("current_price")
        )
        fair_value = _float_or_none(metrics_data.get("fairValue") or metrics_data.get("fair_value"))

        # Determine valuation status
        valuation = str(
            metrics_data.get("valuationStatus")
            or metrics_data.get("valuation_status")
            or data.get("valuationStatus")
            or data.get("valuation_status")
            or "UNKNOWN"
        ).upper()

        # Price multiplier: fair_value / current_price
        multiplier = _float_or_none(
            metrics_data.get("priceMultiplier") or metrics_data.get("price_multiplier")
        )
        if multiplier is None and fair_value and current_price and current_price != 0:
            multiplier = fair_value / current_price

        components = CFVComponentMetrics(
            community_size=_float_or_none(
                metrics_data.get("communitySize") or metrics_data.get("community_size")
            ),
            annual_tx_value=_float_or_none(
                metrics_data.get("annualTxValue") or metrics_data.get("annual_tx_value")
            ),
            annual_tx_count=_float_or_none(
                metrics_data.get("annualTxCount") or metrics_data.get("annual_tx_count")
            ),
            developers=_float_or_none(metrics_data.get("developers")),
        )

        return CFVCoinMetrics(
            symbol=str(data.get("symbol") or metrics_data.get("symbol") or "UNKNOWN").upper(),
            name=str(data.get("name") or metrics_data.get("name") or "Unknown"),
            current_price=current_price,
            fair_value=fair_value,
            cfv_score=_float_or_none(metrics_data.get("cfvScore") or metrics_data.get("cfv_score")),
            valuation_status=valuation,
            price_multiplier=multiplier,
            confidence_level=_float_or_none(
                metrics_data.get("confidence") or metrics_data.get("confidence_level")
            ),
            components=components,
            raw=data,
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _float_or_none(value: Any) -> float | None:
    """Safely cast *value* to float, returning ``None`` on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
