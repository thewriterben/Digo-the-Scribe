"""
CFV Performance Report Generator.

Generates daily CFV performance reports, Battle Plan cross-reference analyses,
and deviation alerts.  All data is presented exactly as received from the API —
never fabricated — in accordance with Digo's anti-hallucination policy.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from digo import config
from digo.cfv_client import CFVClient, CFVCoinMetrics, CFVPortfolioSnapshot
from digo.cfv_data_store import CFVDataStore
from digo.prompts import (
    CFV_ALERT_PROMPT_TEMPLATE,
    CFV_BATTLE_PLAN_ANALYSIS_PROMPT_TEMPLATE,
    CFV_DAILY_REPORT_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


class CFVReporter:
    """
    Generates CFV performance reports for Digital Gold Co.

    The reporter fetches live data via :class:`~digo.cfv_client.CFVClient`,
    stores snapshots via :class:`~digo.cfv_data_store.CFVDataStore`, and
    renders Markdown reports using the LLM (when available) or falls back to
    a plain-text template when no LLM key is configured.

    Usage::

        reporter = CFVReporter(agent._llm)
        report = reporter.generate_daily_report()
        alerts = reporter.check_alerts()
    """

    def __init__(
        self,
        llm_client=None,
        cfv_client: CFVClient | None = None,
        data_store: CFVDataStore | None = None,
    ) -> None:
        self._llm = llm_client
        self._client = cfv_client or CFVClient()
        self._store = data_store or CFVDataStore()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_and_store_snapshot(self) -> CFVPortfolioSnapshot:
        """
        Fetch the current CFV data for all coins, store it, and return it.
        """
        snapshot = self._client.fetch_all_coins()
        if snapshot.coins:
            date = datetime.now(tz=UTC).strftime("%Y-%m-%d")
            self._store.save_snapshot(snapshot, date)
            self._store.append_history(snapshot, date)
        else:
            logger.warning("No CFV data was returned from the API — snapshot not stored.")
        return snapshot

    def generate_daily_report(self, snapshot: CFVPortfolioSnapshot | None = None) -> str:
        """
        Generate a Markdown daily CFV performance report.

        If *snapshot* is ``None`` the reporter fetches fresh data and stores it.
        If the cfv-metrics-agent is unavailable, a notice is returned instead
        of a fabricated report.
        """
        if snapshot is None:
            snapshot = self.fetch_and_store_snapshot()

        if not snapshot.coins:
            return (
                "## CFV Daily Report — Data Unavailable\n\n"
                "The cfv-metrics-agent could not be reached. "
                "Ensure it is running and `CFV_METRICS_API_URL` is correctly configured.\n\n"
                "> [NEEDS VERIFICATION — see Operations Manager]"
            )

        # Build previous snapshot for trend comparison
        prev_snapshot = self._load_previous_snapshot()

        cfv_summary = _format_snapshot_summary(snapshot)
        trend_summary = _format_trend_summary(snapshot, prev_snapshot)
        date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")

        prompt = CFV_DAILY_REPORT_PROMPT_TEMPLATE.format(
            report_date=date_str,
            cfv_summary=cfv_summary,
            trend_summary=trend_summary,
            alert_threshold=config.CFV_ALERT_THRESHOLD,
        )
        return self._render(prompt, fallback=_plain_daily_report(snapshot, date_str))

    def generate_battle_plan_analysis(
        self,
        snapshot: CFVPortfolioSnapshot | None = None,
        battle_plan_excerpts: str = "",
    ) -> str:
        """
        Generate a Markdown analysis cross-referencing CFV metrics against the
        270-Day Battle Plan.

        *battle_plan_excerpts* should be pre-extracted relevant passages from
        the Battle Plan PDF.  If empty, Digo will note that the Battle Plan
        has not been loaded.
        """
        if snapshot is None:
            snapshot = self._client.fetch_all_coins()

        if not snapshot.coins:
            return (
                "## CFV Battle Plan Analysis — Data Unavailable\n\n"
                "No CFV data available. Cannot perform Battle Plan analysis.\n\n"
                "> [NEEDS VERIFICATION — see Operations Manager]"
            )

        cfv_summary = _format_snapshot_summary(snapshot)
        date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")

        if not battle_plan_excerpts:
            battle_plan_excerpts = (
                "[Battle Plan has not been loaded. "
                "Please provide the PDF file and reload resources.]"
            )

        prompt = CFV_BATTLE_PLAN_ANALYSIS_PROMPT_TEMPLATE.format(
            report_date=date_str,
            cfv_summary=cfv_summary,
            battle_plan_excerpts=battle_plan_excerpts,
        )
        return self._render(
            prompt,
            fallback=_plain_battle_plan_analysis(snapshot, date_str),
        )

    def check_alerts(
        self,
        snapshot: CFVPortfolioSnapshot | None = None,
        threshold: float | None = None,
    ) -> tuple[list[dict], str]:
        """
        Check for significant price deviations from CFV fair value.

        Returns a tuple of ``(alert_dicts, alert_report_markdown)``.
        *threshold* defaults to :attr:`digo.config.CFV_ALERT_THRESHOLD`.

        Deviations are computed as:
          ``|current_price - fair_value| / fair_value * 100``
        """
        if snapshot is None:
            snapshot = self._client.fetch_all_coins()

        if threshold is None:
            threshold = config.CFV_ALERT_THRESHOLD

        alerts = _compute_alerts(snapshot.coins, threshold)

        date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        if alerts:
            self._store.save_alerts(alerts, date_str)

        if not alerts:
            report = (
                f"## CFV Alerts — {date_str}\n\n"
                f"✅ No significant deviations detected (threshold: {threshold:.0f}%).\n"
            )
            return [], report

        cfv_summary = _format_snapshot_summary(snapshot)
        alerts_summary = _format_alerts_summary(alerts)
        prompt = CFV_ALERT_PROMPT_TEMPLATE.format(
            report_date=date_str,
            alerts_summary=alerts_summary,
            cfv_summary=cfv_summary,
            alert_threshold=threshold,
        )
        report = self._render(prompt, fallback=_plain_alert_report(alerts, date_str, threshold))
        return alerts, report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _render(self, prompt: str, fallback: str) -> str:
        """Call the LLM with *prompt* or return *fallback* if LLM unavailable."""
        if self._llm is None:
            logger.info("LLM not available — returning template-based CFV report.")
            return fallback
        try:
            from digo import config as cfg
            from digo.prompts import SYSTEM_PROMPT

            response = self._llm.messages.create(
                model=cfg.LLM_MODEL,
                max_tokens=cfg.LLM_MAX_TOKENS,
                temperature=cfg.LLM_TEMPERATURE,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                timeout=120.0,
            )
            text_blocks = [block.text for block in response.content if hasattr(block, "text")]
            return "\n".join(text_blocks)
        except Exception as exc:
            logger.warning("LLM call failed for CFV report: %s — using fallback.", exc)
            return fallback

    def _load_previous_snapshot(self) -> CFVPortfolioSnapshot | None:
        """Return the most recent stored snapshot (for trend comparison)."""
        try:
            return self._store.load_latest_snapshot()
        except Exception as exc:
            logger.warning("Could not load previous CFV snapshot: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Formatting helpers (used for LLM prompt context and plain-text fallback)
# ---------------------------------------------------------------------------


def _format_snapshot_summary(snapshot: CFVPortfolioSnapshot) -> str:
    """Format a CFV portfolio snapshot as a Markdown table."""
    lines = [
        f"*Fetched at: {snapshot.fetched_at}*\n",
        "| Symbol | Name | Current Price | Fair Value | CFV Score | Status | Multiplier |",
        "|--------|------|--------------|-----------|-----------|--------|------------|",
    ]
    for coin in snapshot.coins:
        price = f"${coin.current_price:,.4f}" if coin.current_price is not None else "N/A"
        fv = f"${coin.fair_value:,.4f}" if coin.fair_value is not None else "N/A"
        score = f"{coin.cfv_score:.2f}" if coin.cfv_score is not None else "N/A"
        mult = f"{coin.price_multiplier:.2f}x" if coin.price_multiplier is not None else "N/A"
        lines.append(
            f"| {coin.symbol} | {coin.name} | {price} | {fv} | {score} | "
            f"{coin.valuation_status} | {mult} |"
        )
    return "\n".join(lines)


def _format_trend_summary(
    current: CFVPortfolioSnapshot,
    previous: CFVPortfolioSnapshot | None,
) -> str:
    """Describe price/fair-value changes between two snapshots."""
    if previous is None:
        return "*No previous snapshot available for trend comparison.*"

    prev_by_symbol = {c.symbol: c for c in previous.coins}
    lines = [
        "| Symbol | Price Change | Fair Value Change |",
        "|--------|------------|-----------------|",
    ]
    any_changes = False
    for coin in current.coins:
        prev = prev_by_symbol.get(coin.symbol)
        if prev is None:
            continue
        price_chg = _pct_change(prev.current_price, coin.current_price)
        fv_chg = _pct_change(prev.fair_value, coin.fair_value)
        if price_chg is not None or fv_chg is not None:
            pc_str = f"{price_chg:+.2f}%" if price_chg is not None else "N/A"
            fc_str = f"{fv_chg:+.2f}%" if fv_chg is not None else "N/A"
            lines.append(f"| {coin.symbol} | {pc_str} | {fc_str} |")
            any_changes = True

    if not any_changes:
        return "*No comparable coins found in the previous snapshot.*"
    return "\n".join(lines)


def _format_alerts_summary(alerts: list[dict]) -> str:
    """Format a list of alert dicts as a readable summary."""
    lines = []
    for a in alerts:
        lines.append(
            f"- **{a['symbol']}** ({a['name']}): current price ${a['current_price']:,.4f}, "
            f"fair value ${a['fair_value']:,.4f}, "
            f"deviation {a['deviation_pct']:+.1f}%, "
            f"status: {a['valuation_status']}"
        )
    return "\n".join(lines)


def _compute_alerts(coins: list[CFVCoinMetrics], threshold: float) -> list[dict]:
    """Return alert dicts for coins whose price deviates from fair value by ≥ threshold %."""
    alerts = []
    for coin in coins:
        if coin.current_price is None or coin.fair_value is None or coin.fair_value == 0:
            continue
        deviation_pct = (coin.current_price - coin.fair_value) / coin.fair_value * 100
        if abs(deviation_pct) >= threshold:
            alerts.append(
                {
                    "symbol": coin.symbol,
                    "name": coin.name,
                    "current_price": coin.current_price,
                    "fair_value": coin.fair_value,
                    "deviation_pct": deviation_pct,
                    "valuation_status": coin.valuation_status,
                    "price_multiplier": coin.price_multiplier,
                }
            )
    return alerts


def _pct_change(old: float | None, new: float | None) -> float | None:
    """Return percentage change from *old* to *new*, or ``None``."""
    if old is None or new is None or old == 0:
        return None
    return (new - old) / old * 100


# ---------------------------------------------------------------------------
# Plain-text fallbacks (used when LLM is unavailable)
# ---------------------------------------------------------------------------


def _plain_daily_report(snapshot: CFVPortfolioSnapshot, date_str: str) -> str:
    summary = _format_snapshot_summary(snapshot)
    return (
        f"## CFV Daily Performance Report — {date_str}\n\n"
        "*(LLM unavailable — template-based report)*\n\n"
        "### Portfolio Snapshot\n\n"
        f"{summary}\n\n"
        "> Data sourced directly from cfv-metrics-agent REST API. "
        "No values have been fabricated or estimated."
    )


def _plain_battle_plan_analysis(snapshot: CFVPortfolioSnapshot, date_str: str) -> str:
    summary = _format_snapshot_summary(snapshot)
    return (
        f"## CFV vs. 270-Day Battle Plan Analysis — {date_str}\n\n"
        "*(LLM unavailable — template-based analysis)*\n\n"
        "### Current CFV Portfolio\n\n"
        f"{summary}\n\n"
        "> [NEEDS VERIFICATION — see Operations Manager]\n"
        "> Full cross-reference requires the LLM. "
        "Please configure ANTHROPIC_API_KEY and rerun."
    )


def _plain_alert_report(alerts: list[dict], date_str: str, threshold: float) -> str:
    summary = _format_alerts_summary(alerts)
    return (
        f"## CFV Performance Alerts — {date_str}\n\n"
        f"⚠️ **{len(alerts)} deviation alert(s) detected** "
        f"(threshold: ≥{threshold:.0f}% from CFV fair value)\n\n"
        f"{summary}\n\n"
        "> Data sourced directly from cfv-metrics-agent REST API. "
        "No values have been fabricated or estimated."
    )
