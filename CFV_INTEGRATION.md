# CFV Metrics Integration

This document explains how Digo the Scribe integrates with the
[`cfv-metrics-agent`](https://github.com/thewriterben/cfv-metrics-agent) to
track and understand Crypto Fair Value (CFV) performance and its relation to
the digitalgold.co CFV Fund Performance, cross-referenced against the
270-Day Battle Plan.

---

## How the integration works

```
┌──────────────────┐   REST API (read-only)    ┌──────────────────────┐
│  Digo-the-Scribe │ ◄── GET /api/metrics/* ── │  cfv-metrics-agent   │
│  (Python)        │                           │  (TypeScript/Node.js)│
│                  │                           │                      │
│  • Daily reports │                           │  CoinGecko           │
│  • Battle Plan   │                           │  Etherscan           │
│    analysis      │                           │  GitHub              │
│  • Alert checks  │                           │  70/10/10/10 formula │
│  • Meeting notes │                           │  MySQL + scheduler   │
└──────────────────┘                           └──────────────────────┘
         │
         ▼
  output/cfv_data/
  ├── daily/YYYY-MM-DD.json
  ├── history.csv
  └── alerts/YYYY-MM-DD_alerts.json
```

The integration is **read-only**: Digo reads from cfv-metrics-agent's REST
API and never writes back to it.

### CFV Formula

The cfv-metrics-agent calculates Crypto Fair Value using the
**70/10/10/10 formula**:

| Component             | Weight |
|-----------------------|--------|
| Community Size        | 70%    |
| Annual Transaction Value | 10% |
| Annual Transaction Count | 10% |
| Developers            | 10%    |

Digo uses this data to assess whether each DGF coin is **UNDERVALUED**,
**OVERVALUED**, or **FAIR** relative to its calculated fair value.

---

## Configuration

Copy `.env.example` to `.env` and set the following variables:

| Variable             | Default                    | Description |
|----------------------|----------------------------|-------------|
| `CFV_METRICS_API_URL` | `http://localhost:3000`    | Base URL of cfv-metrics-agent REST API |
| `CFV_ALERT_THRESHOLD` | `20.0`                    | % deviation from fair value that triggers an alert |
| `CFV_COINS`          | `BTC,ETH,DASH,NANO,...`    | Comma-separated list of DGF coins to track |

```bash
# .env
CFV_METRICS_API_URL=http://localhost:3000
CFV_ALERT_THRESHOLD=20.0
CFV_COINS=BTC,ETH,DASH,NANO,NEAR,ICP,XLM,XRP,ADA,DOT,LINK
```

---

## Running cfv-metrics-agent alongside Digo

1. Clone and set up cfv-metrics-agent (see its own README):

   ```bash
   git clone https://github.com/thewriterben/cfv-metrics-agent.git
   cd cfv-metrics-agent
   npm install
   cp .env.example .env   # fill in API keys
   npm run start
   ```

2. Confirm it is running:

   ```bash
   curl http://localhost:3000/api/rate-limits/status
   ```

3. Run Digo with CFV commands (see below).

---

## CLI commands

### `digo cfv-snapshot`

Take a snapshot of current CFV metrics for all DGF coins and store it locally.

```bash
digo cfv-snapshot
```

Output:
```
Taking CFV snapshot for all DGF coins…
Snapshot taken: 11 coin(s) stored.
  BTC     price=$65,000.0000  fair_value=$72,000.0000  status=UNDERVALUED
  ETH     price=$3,200.0000   fair_value=$2,800.0000   status=OVERVALUED
  ...
```

### `digo cfv-report`

Generate a daily CFV performance report (stored in `output/reports/`).

```bash
digo cfv-report
```

### `digo cfv-alerts`

Check for coins whose price deviates significantly from CFV fair value.

```bash
digo cfv-alerts
```

Output (when alerts are triggered):
```
⚠  2 alert(s) triggered!

## CFV Performance Alerts — 2026-03-28

⚠️ 2 deviation alert(s) detected (threshold: ≥20% from CFV fair value)

- **BTC** (Bitcoin): current price $50,000.0000, fair value $72,000.0000,
  deviation -30.6%, status: UNDERVALUED
```

### `digo cfv-analysis`

Generate a Markdown analysis cross-referencing CFV metrics against the
270-Day Battle Plan.

```bash
digo cfv-analysis
```

---

## Automated daily report (GitHub Actions)

The workflow at `.github/workflows/cfv-daily-report.yml` runs every day at
08:00 UTC and:

1. Takes a CFV snapshot for all DGF coins.
2. Generates the daily CFV performance report.
3. Checks for alerts (price deviations ≥ `CFV_ALERT_THRESHOLD`).
4. Commits updated snapshot/report files to the repository.
5. Creates a GitHub Issue (labelled `cfv-alert`) if any alerts fire.

### Required secrets / variables

| Name | Type | Description |
|------|------|-------------|
| `ANTHROPIC_API_KEY` | Secret | Anthropic API key for LLM calls |
| `CFV_METRICS_API_URL` | Secret | URL of cfv-metrics-agent (if not localhost) |
| `OPS_MANAGER_EMAIL` | Secret | Escalation email for Benjamin Snider |
| `CFV_ALERT_THRESHOLD` | Variable | Alert threshold (default: 20) |
| `CFV_COINS` | Variable | Coin list override |

---

## Data storage

All CFV data is stored under `output/cfv_data/` (gitignored by default):

| Path | Format | Description |
|------|--------|-------------|
| `output/cfv_data/daily/YYYY-MM-DD.json` | JSON | Full snapshot per day |
| `output/cfv_data/history.csv` | CSV (append-only) | Per-coin price/value history |
| `output/cfv_data/alerts/YYYY-MM-DD_alerts.json` | JSON | Alert records |

---

## Sample daily report output

```markdown
## CFV Daily Performance Report — 2026-03-28

### Executive Summary

Today's CFV analysis shows BTC trading at a significant discount to its
fair value (−9.7%), while ETH continues to trade above fair value (+14.3%).
No coins have breached the 20% alert threshold.

### Portfolio Snapshot

| Symbol | Name | Current Price | Fair Value | CFV Score | Status | Multiplier |
|--------|------|--------------|-----------|-----------|--------|------------|
| BTC | Bitcoin | $65,000.0000 | $72,000.0000 | 85.50 | UNDERVALUED | 1.11x |
| ETH | Ethereum | $3,200.0000 | $2,800.0000 | 78.20 | OVERVALUED | 0.88x |
...

### Trend Analysis

| Symbol | Price Change | Fair Value Change |
|--------|------------|-----------------|
| BTC | +2.30% | +0.50% |
| ETH | -1.20% | +0.10% |

### Confidence Notes

All data sourced directly from cfv-metrics-agent REST API. No values
have been fabricated or estimated.
```

---

## Alert thresholds and customisation

The default alert threshold is **±20%** deviation from CFV fair value.

To change it:
- Set `CFV_ALERT_THRESHOLD=15.0` in your `.env` for stricter monitoring.
- Set it as a GitHub Actions variable (`CFV_ALERT_THRESHOLD`) for the daily workflow.

When an alert fires, Digo:
1. Stores the alert JSON in `output/cfv_data/alerts/`.
2. Generates an alert report (Markdown).
3. Creates a GitHub Issue (in the automated workflow).

---

## Anti-hallucination policy

In accordance with Digo's core anti-hallucination policy:

- All CFV figures are presented **verbatim** from the API — never adjusted, rounded beyond
  normal display precision, or estimated.
- If cfv-metrics-agent is unavailable, Digo returns a clear notice rather than using stale
  or fabricated data.
- If the LLM is unavailable, a template-based report is generated from raw API data.
- Any claim that cannot be confirmed from the API or Battle Plan is flagged
  `[NEEDS VERIFICATION — see Operations Manager]`.
