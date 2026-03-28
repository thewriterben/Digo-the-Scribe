"""
CFV data persistence.

Stores daily CFV snapshots, historical trend data, and alert records locally
so that Digo can perform trend analysis without re-querying the API.

Directory layout::

    output/cfv_data/
    ├── daily/
    │   └── YYYY-MM-DD.json      # Full CFV snapshot per day
    ├── history.csv              # Append-only per-coin price/value history
    └── alerts/
        └── YYYY-MM-DD_alerts.json  # Alert records for that day
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from digo import config
from digo.cfv_client import CFVCoinMetrics, CFVPortfolioSnapshot

logger = logging.getLogger(__name__)

_CSV_HEADERS = [
    "date",
    "symbol",
    "name",
    "current_price",
    "fair_value",
    "cfv_score",
    "valuation_status",
    "price_multiplier",
    "confidence_level",
]


class CFVDataStore:
    """
    Persists CFV portfolio snapshots, historical data, and alerts.

    All paths default to :attr:`digo.config.CFV_DATA_DIR` but can be
    overridden for testing.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = base_dir or config.CFV_DATA_DIR
        self._daily_dir = self._base / "daily"
        self._alerts_dir = self._base / "alerts"
        self._history_file = self._base / "history.csv"

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def save_snapshot(self, snapshot: CFVPortfolioSnapshot, date: str | None = None) -> Path:
        """
        Persist *snapshot* as a JSON file under ``daily/YYYY-MM-DD.json``.

        If *date* is omitted the current UTC date is used.
        """
        date = date or datetime.now(tz=UTC).strftime("%Y-%m-%d")
        self._daily_dir.mkdir(parents=True, exist_ok=True)
        out_path = self._daily_dir / f"{date}.json"

        payload = {
            "fetched_at": snapshot.fetched_at,
            "api_url": snapshot.api_url,
            "coins": [_coin_to_dict(c) for c in snapshot.coins],
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("CFV snapshot saved to %s", out_path)
        return out_path

    def load_snapshot(self, date: str) -> CFVPortfolioSnapshot | None:
        """
        Load the snapshot for *date* (``YYYY-MM-DD``).

        Returns ``None`` if no snapshot exists for that date.
        """
        path = self._daily_dir / f"{date}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read CFV snapshot %s: %s", path, exc)
            return None

        return CFVPortfolioSnapshot(
            fetched_at=payload.get("fetched_at", ""),
            api_url=payload.get("api_url", ""),
            coins=[_dict_to_coin(c) for c in payload.get("coins", [])],
        )

    def load_latest_snapshot(self) -> CFVPortfolioSnapshot | None:
        """Return the most recent snapshot, or ``None`` if none exist."""
        if not self._daily_dir.exists():
            return None
        files = sorted(self._daily_dir.glob("*.json"), reverse=True)
        for f in files:
            snapshot = self.load_snapshot(f.stem)
            if snapshot is not None:
                return snapshot
        return None

    def list_snapshot_dates(self) -> list[str]:
        """Return all stored snapshot dates (``YYYY-MM-DD``) in ascending order."""
        if not self._daily_dir.exists():
            return []
        return sorted(f.stem for f in self._daily_dir.glob("*.json"))

    # ------------------------------------------------------------------
    # Historical CSV
    # ------------------------------------------------------------------

    def append_history(self, snapshot: CFVPortfolioSnapshot, date: str | None = None) -> None:
        """
        Append per-coin rows from *snapshot* to the history CSV.

        Creates the file and writes headers if it does not yet exist.
        """
        date = date or datetime.now(tz=UTC).strftime("%Y-%m-%d")
        self._base.mkdir(parents=True, exist_ok=True)

        write_header = not self._history_file.exists()
        with self._history_file.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_CSV_HEADERS)
            if write_header:
                writer.writeheader()
            for coin in snapshot.coins:
                writer.writerow(
                    {
                        "date": date,
                        "symbol": coin.symbol,
                        "name": coin.name,
                        "current_price": coin.current_price,
                        "fair_value": coin.fair_value,
                        "cfv_score": coin.cfv_score,
                        "valuation_status": coin.valuation_status,
                        "price_multiplier": coin.price_multiplier,
                        "confidence_level": coin.confidence_level,
                    }
                )
        logger.info("Appended %d coin rows to history CSV", len(snapshot.coins))

    def load_history(self) -> list[dict[str, str]]:
        """
        Return all rows from the history CSV as a list of dicts.

        Returns an empty list if the file does not exist.
        """
        if not self._history_file.exists():
            return []
        try:
            with self._history_file.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                return list(reader)
        except OSError as exc:
            logger.warning("Could not read history CSV: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def save_alerts(self, alerts: list[dict], date: str | None = None) -> Path:
        """
        Persist *alerts* as a JSON file under ``alerts/YYYY-MM-DD_alerts.json``.

        *alerts* is a list of plain dicts describing each alert.
        """
        date = date or datetime.now(tz=UTC).strftime("%Y-%m-%d")
        self._alerts_dir.mkdir(parents=True, exist_ok=True)
        out_path = self._alerts_dir / f"{date}_alerts.json"

        payload = {
            "date": date,
            "alerts": alerts,
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Saved %d alert(s) to %s", len(alerts), out_path)
        return out_path

    def load_alerts(self, date: str) -> list[dict]:
        """
        Load alerts for *date* (``YYYY-MM-DD``).

        Returns an empty list if no alert file exists for that date.
        """
        path = self._alerts_dir / f"{date}_alerts.json"
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload.get("alerts", [])
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read alerts file %s: %s", path, exc)
            return []


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _coin_to_dict(coin: CFVCoinMetrics) -> dict:
    """Convert a :class:`CFVCoinMetrics` to a JSON-serialisable dict."""
    d = asdict(coin)
    # Drop raw API payload to keep snapshots lightweight
    d.pop("raw", None)
    return d


def _dict_to_coin(d: dict) -> CFVCoinMetrics:
    """Reconstruct a :class:`CFVCoinMetrics` from a stored dict."""
    from digo.cfv_client import CFVComponentMetrics

    comp_data = d.get("components", {})
    components = CFVComponentMetrics(
        community_size=comp_data.get("community_size"),
        annual_tx_value=comp_data.get("annual_tx_value"),
        annual_tx_count=comp_data.get("annual_tx_count"),
        developers=comp_data.get("developers"),
    )
    return CFVCoinMetrics(
        symbol=d.get("symbol", "UNKNOWN"),
        name=d.get("name", "Unknown"),
        current_price=d.get("current_price"),
        fair_value=d.get("fair_value"),
        cfv_score=d.get("cfv_score"),
        valuation_status=d.get("valuation_status", "UNKNOWN"),
        price_multiplier=d.get("price_multiplier"),
        confidence_level=d.get("confidence_level"),
        components=components,
    )
