# Tech Analyzer — Paper Trading Dashboard

Intraday paper trading system for NSE stocks using Upstox live data,
candlestick pattern detection, and a real-time web dashboard.

---

## Requirements

- Python 3.11+
- Node.js 18+
- [TA-Lib C library](https://ta-lib.org/install/) (must be installed before `pip install`)
- Upstox developer account — [developer.upstox.com](https://developer.upstox.com)

---

## One-time setup

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd tech-analyzer
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
```

### 2. Install Python dependencies

```bash
pip install -e .
```

### 3. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in your Upstox API credentials:

```
UPSTOX_API_KEY=your-api-key
UPSTOX_API_SECRET=your-api-secret
UPSTOX_REDIRECT_URI=http://127.0.0.1:8000/callback
```

### 4. Install frontend dependencies

```bash
cd web
npm install
cd ..
```

---

## Daily workflow

### Step 1 — Start the backend server

```bash
uvicorn tech_analyzer.web.app:app --reload --port 8000
```

### Step 2 — Authenticate with Upstox (once per day)

Upstox tokens expire at end of each trading day.

With the server running, open this in your browser:

```
http://localhost:8000/api/auth/url
```

Copy the URL from the JSON response, open it, log in with your Upstox credentials.
You will be redirected back and shown a **"Login successful"** page.
The token is saved automatically — no restart needed.

> **Check auth status:** `http://localhost:8000/api/auth/status`

### Step 3 — Open the dashboard

```
http://localhost:8000
```

Click **▶ Start**, choose your watchlist, interval, and capital, then start the session.

---

## Development mode (hot reload)

Run two terminals simultaneously:

**Terminal 1 — backend (auto-reloads on Python changes):**
```bash
uvicorn tech_analyzer.web.app:app --reload --port 8000
```

**Terminal 2 — frontend (instant browser hot-reload):**
```bash
cd web
npm run dev
```

Open `http://localhost:5173` — API and WebSocket calls are proxied to port 8000.
No `npm run build` needed while developing.

---

## Production build

When you want the backend to serve the frontend directly at port 8000:

```bash
cd web
npm run build
cd ..
uvicorn tech_analyzer.web.app:app --port 8000
```

---

## CLI usage (without web UI)

```bash
# Authenticate
python -m tech_analyzer --auth

# Paper trade (Bank Nifty, 15m candles, ₹2L capital)
python -m tech_analyzer --paper --watchlist nifty_bank --interval 15m --capital 200000

# Backtest
python -m tech_analyzer --symbol RELIANCE.NS --backtest
```

---

## Project structure

```
tech_analyzer/
  data/           Upstox API: live candles, LTP, instrument lookup, auth
  patterns/       Candlestick pattern detection (TA-Lib)
  trading/        Paper trading: portfolio, engine, session, EOD report
  web/            FastAPI backend: REST API, WebSocket broadcaster, auth
  screener/       Watchlists (nifty_bank, nifty50)
  cli.py          Entry point for --auth / --paper / --backtest

web/              React + Vite frontend
  src/
    components/   SessionControls, SymbolTable, TradeFeed, CandleChart, ...
    ws/           WebSocket client (useWebSocket hook, event types)
    api/          REST API client

output/
  paper_trading/  EOD charts saved here (PNG per instrument, per day)

~/.tech_analyzer/
  upstox_token.json     Cached auth token
  paper_portfolio.json  Persisted portfolio state (survives restarts)
  instruments_*.csv     Cached Upstox instrument master
```

---

## Configuration reference

| Parameter | Default | Description |
|---|---|---|
| Watchlist | `nifty_bank` | `nifty_bank` or `nifty50` |
| Interval | `15m` | `1m` `5m` `15m` `30m` `1h` |
| Capital | ₹1,00,000 | Starting paper capital |
| Target % | 1.5% | Take-profit per trade |
| Stop % | 0.8% | Stop-loss per trade |
| Trend Filter | on | Only take trades aligned with EMA trend |
| Fresh Start | off | Reset portfolio to starting capital on session start |

---

## Notes

- The session runs from **09:15 to 15:30 IST**, Monday–Friday.
  All open positions are force-closed at **15:25**.
- EOD charts and a P&L statement are generated at session end under `output/paper_trading/YYYY-MM-DD/`.
- Portfolio state is persisted to `~/.tech_analyzer/paper_portfolio.json` and survives server restarts.
- The **Stop** button interrupts the current inter-candle sleep immediately.
