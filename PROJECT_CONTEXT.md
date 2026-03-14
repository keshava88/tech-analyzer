# tech-analyzer — Project Context

## Idea
A Python CLI tool for **stock technical analysis focused on the Indian market (NSE/BSE)**.
The first cut is a **candlestick pattern recognition engine** — given a stock ticker, detect all
known candlestick patterns in its historical price data, classify them as bullish/bearish,
indicate candle colour and signal strength, and optionally generate annotated charts.

---

## Tech Stack Decisions

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.11 | Modern typing support, wide library ecosystem |
| Pattern detection | **TA-Lib 0.6.x** | Originally planned pandas-ta but its PyPI repo was taken down; ta-lib has 61 built-in CDL functions, pre-built wheels (no C install needed) |
| Historical data | **yfinance** | Free, no auth, covers NSE (`.NS`) and BSE (`.BO`), up to 1-min OHLCV |
| Live data (future) | **Upstox API v2** | Free for account holders, REST + WebSocket, good Python SDK |
| Charting | **mplfinance** | Candlestick charts with volume, supports addplot overlays for markers |
| Package management | pip + pyproject.toml | Standard, no extra tooling required |
| Linting | ruff | Fast, modern |
| Testing | pytest + pytest-cov | Standard |

---

## Project Structure

```
tech-analyzer/
├── tech_analyzer/
│   ├── data/
│   │   ├── historical.py     # yfinance OHLCV fetcher (DONE)
│   │   └── live.py           # Upstox live feed (TODO)
│   ├── patterns/
│   │   └── detector.py       # TA-Lib CDL pattern detection (DONE)
│   ├── charts/
│   │   └── plotter.py        # mplfinance chart generator (DONE)
│   ├── alerts/
│   │   └── notifier.py       # Alert delivery (TODO)
│   ├── cli.py                # argparse CLI entry point (DONE)
│   └── __main__.py           # python -m tech_analyzer support
├── tests/
├── output/                   # gitignored — generated charts go here
│   └── charts/
├── .env.example              # Upstox API key template
├── pyproject.toml
└── PROJECT_CONTEXT.md        # this file
```

---

## What's Built (v0.1)

### `data/historical.py`
- `fetch(symbol, period, interval)` — downloads OHLCV from yfinance
- Validates empty responses, returns lowercase-column DataFrame with DatetimeIndex
- NSE tickers use `.NS` suffix (e.g. `RELIANCE.NS`), BSE use `.BO`

### `patterns/detector.py`
- 22 curated patterns across single / two / three candle formations
- `detect(df)` → all signals across full history
- `detect_latest(df)` → signals on the most recent candle only
- Output columns: `date`, `pattern`, `signal`, `value`, `candle`, `strength`
  - `candle` — `green` or `red` (close >= open)
  - `strength` — `strong` / `weak` / `-` based on whether candle colour aligns with signal direction
  - e.g. a red-bodied Hammer is `bullish` but `weak`; a green-bodied Hammer is `strong`

### `charts/plotter.py`
- `plot_signal(df, signal, window, save_dir)` — generates a single PNG
- Shows ±window candles around the pattern candle
- Green ▲ below candle for bullish, red ▼ above for bearish
- Subtitle shows candle colour + strength (e.g. `Candle: RED | Strength: WEAK`)
- `plot_all_signals(df, signals, ...)` — batch generates all charts

### `cli.py`
```bash
python -m tech_analyzer RELIANCE.NS                          # all patterns, 6mo history
python -m tech_analyzer TCS.NS --period 3mo --interval 1d   # custom period
python -m tech_analyzer INFY.NS --latest                     # latest candle only
python -m tech_analyzer RELIANCE.NS --chart --window 5       # generate charts
python -m tech_analyzer RELIANCE.NS --patterns CDLHAMMER CDLENGULFING  # specific patterns
```

---

## Setup on a New Machine

```bash
git clone https://github.com/keshava88/tech-analyzer.git
cd tech-analyzer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" --pre    # --pre needed for mplfinance (pre-release on PyPI)
```

> **Note:** If your pip index is a corporate proxy (Artifactory etc.) that doesn't have
> `ta-lib`, install directly: `pip install ta-lib --index-url https://pypi.org/simple/`

---

## Known Issues / Gotchas
- `mplfinance` only exists as pre-release on PyPI — use `--pre` flag or pin to `0.12.10b0`
- `pandas-ta` repo was taken down — **do not use**, replaced by `ta-lib`
- SSH (port 22) may be blocked on corporate networks — use HTTPS remote for git push
- TA-Lib CDL function names use old-style format: `CDLHAMMER` not `CDL_HAMMER`

---

## Planned Next Steps (Priority Order)

### 1. Trend Context Filter *(high impact)*
Patterns without trend context generate a lot of noise.
- Add EMA/SMA trend classifier to `detector.py`
- Only surface patterns that align with the prevailing trend
- e.g. Hammer is only meaningful signal at the bottom of a downtrend

### 2. Multi-Stock Screener
- Accept a watchlist (Nifty 50, custom list) instead of a single symbol
- Scan all stocks and report only those with patterns on the latest candle
- Useful for a daily pre-market morning scan

### 3. Support / Resistance Annotation on Charts
- Detect key S/R levels (swing highs/lows, round numbers)
- Annotate on charts so patterns at S/R levels are clearly visible
- Patterns forming at S/R carry significantly more weight

### 4. Intraday Mode (15m / 1h candles) via Upstox
- Implement `data/live.py` using Upstox API OAuth + WebSocket
- Stream live ticks → aggregate to OHLCV → run detector in real-time
- `.env` file already scaffolded for `UPSTOX_API_KEY` / `UPSTOX_API_SECRET`

### 5. Pattern Backtesting / Hit Rate
- For each historical pattern signal, measure price change over next N candles
- Compute per-pattern hit rate on a given stock
- Surfaces which patterns have actually worked on a specific stock historically

### 6. Alerts / Notifications
- Run screener on a schedule (cron / APScheduler)
- Push Telegram bot message when a strong pattern fires on a watched stock
- Telegram is easiest: `python-telegram-bot` library

---

## GitHub
Repository: https://github.com/keshava88/tech-analyzer
