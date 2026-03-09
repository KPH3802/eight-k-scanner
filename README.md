# eight-k-scanner

Automated SEC 8-K Item 1.01 Material Agreement scanner with statistical signal detection and actionable email alerts.

## What It Detects

Scans SEC EDGAR daily for 8-K Item 1.01 (Material Agreement) filings and filters them for short-selling signals using backtested L2 criteria:

- **Signal:** -2.89% avg alpha at 5 days | t-stat = -9.98 | 59.9% win rate
- **Backtest:** 556 trades, 2020-2025, $25K account
- **Direction:** SHORT — stock declines after material agreement filing
- **Regime filter:** VIX 15-30 only (signal degrades outside this window)
- **Price filter:** $50+ stocks only
- **Cross-signal:** Optional Form 4 insider sell confirmation (+2 score bonus)

## Email Alert Format

Each alert email includes:
- **TRADE section** (Score 2+): actionable signals with pre-calculated action lines
- **WATCH section** (Score 1): low-conviction signals for monitoring only
- **VIX warning banner** if VIX ≥ 25
- Subject line includes actual ticker symbols: `8-K SHORT: MOG-B, ITT, LDOS`

Action line format:
```
SHORT at Mon Mar 9 open  |  Stop $354.74  |  Exit Mon Mar 16
```

## Scoring System

| Score | Condition | Action |
|-------|-----------|--------|
| 1 | Base pass (price + VIX + sector) | WATCH only |
| 2 | Large cap ($100+) OR optimal VIX (15-20) | TRADE — standard size |
| 3 | Large cap + optimal VIX | TRADE — full size |
| 4+ | Any above + insider sell confirmation (90d) | TRADE — max size |

## Architecture

```
eight_k_scanner/
├── main.py              # Entry point — orchestrates fetch, filter, alert
├── edgar_fetcher.py     # SEC EDGAR full-text search (EFTS API)
├── signal_filter.py     # L2 filters: price, VIX, sector, insider cross-ref
├── database.py          # SQLite — tracks filings, prevents duplicate alerts
├── emailer.py           # HTML email builder and sender
├── config_example.py    # Configuration template
└── requirements.txt     # Dependencies
```

## Setup

```bash
git clone https://github.com/KPH3802/eight-k-scanner.git
cd eight-k-scanner
pip install -r requirements.txt
cp config_example.py config.py
# Edit config.py with your email credentials and paths
```

## Usage

```bash
# Live scan (sends email)
python3 main.py

# Dry run (no email, saves preview to file)
python3 main.py --dry-run

# Test email with sample data
python3 main.py --test-email

# Extended lookback window
python3 main.py --lookback 5
```

## Deployment

Scheduled on PythonAnywhere at **21:45 UTC daily**:
```
cd /home/KPH3802/eight_k_scanner && python3 main.py
```

## Backtest Results

| Metric | Value |
|--------|-------|
| Period | 2020–2025 |
| Trades | 556 |
| Avg Alpha (5d) | -2.89% |
| t-statistic | -9.98 |
| Win Rate | 59.9% |
| Total Alpha | +$20,526 (2% sizing, $25K account) |

Signal strengthens with insider sell confirmation (L3 cross-signal): -1.32% incremental alpha at 20 days (t = -4.21).

## Dependencies

- `yfinance` — price and sector data
- `requests` — SEC EDGAR API calls
- Standard library: `smtplib`, `sqlite3`, `argparse`

## Disclaimer

This tool is for research and educational purposes only. Not financial advice. Past backtested performance does not guarantee future results. All trading involves risk of loss.

## License

MIT
