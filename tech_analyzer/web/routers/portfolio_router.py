from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Query

from tech_analyzer.trading.portfolio import Portfolio, DEFAULT_PORTFOLIO_FILE

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("")
def get_portfolio():
    port = Portfolio.load(DEFAULT_PORTFOLIO_FILE)
    return {
        "summary": port.summary(),
        "positions": [asdict(p) for p in port.positions],
        "closed_trades": [asdict(t) for t in port.closed_trades],
    }


@router.get("/trades")
def get_trades(date_filter: str | None = Query(default=None, alias="date")):
    port = Portfolio.load(DEFAULT_PORTFOLIO_FILE)
    trades = [asdict(t) for t in port.closed_trades]
    if date_filter:
        trades = [t for t in trades if t["entry_date"][:10] == date_filter
                  or t["exit_date"][:10] == date_filter]
    return {"trades": trades}


@router.get("/candles/{symbol:path}")
def get_candles(symbol: str, interval: str = "15m"):
    from tech_analyzer.data.live import fetch
    import pandas as pd

    try:
        df = fetch(symbol, interval=interval)
    except Exception as e:
        return {"symbol": symbol, "candles": [], "error": str(e)}

    # Keep only today's candles for the chart
    today = date.today()
    df_today = df[df.index.date == today]
    if df_today.empty:
        df_today = df  # fallback to all data if market closed

    candles = [
        {
            "time": int(row.Index.timestamp()),
            "open":  round(row.open,  2),
            "high":  round(row.high,  2),
            "low":   round(row.low,   2),
            "close": round(row.close, 2),
        }
        for row in df_today.itertuples()
    ]
    return {"symbol": symbol, "interval": interval, "candles": candles}
