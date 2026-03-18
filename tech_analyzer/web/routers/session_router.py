from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tech_analyzer.web.state import get_state, SessionStatus
from tech_analyzer.web.session_runner import start_session, stop_session
from tech_analyzer.web.market import market_status
from tech_analyzer.trading.portfolio import Portfolio, DEFAULT_PORTFOLIO_FILE

router = APIRouter(prefix="/session", tags=["session"])


class StartRequest(BaseModel):
    symbols: list[str] | None = None
    watchlist: str | None = None
    interval: str = "15m"
    capital: float = 100_000.0
    target_pct: float = 2.0
    stoploss_pct: float = 1.0
    patterns: list[str] | None = None
    trend_filter: bool = True
    fresh: bool = False


@router.post("/start")
async def session_start(req: StartRequest):
    import asyncio as _asyncio
    state = get_state()
    if state.status == SessionStatus.RUNNING:
        raise HTTPException(400, "Session already running.")

    symbols = req.symbols or []
    if req.watchlist and not symbols:
        from tech_analyzer.screener.watchlists import load
        symbols = load(req.watchlist)
    if not symbols:
        raise HTTPException(400, "Provide symbols or a watchlist.")

    loop = _asyncio.get_running_loop()
    start_session({
        "symbols": symbols,
        "interval": req.interval,
        "capital": req.capital,
        "target_pct": req.target_pct,
        "stoploss_pct": req.stoploss_pct,
        "patterns": req.patterns,
        "trend_filter": req.trend_filter,
        "fresh": req.fresh,
    }, loop)
    return {"status": "started", "symbols": symbols, "interval": req.interval}


@router.post("/stop")
def session_stop():
    stop_session()
    return {"status": "stop_requested"}


@router.post("/reset")
def session_reset(capital: float = 100_000.0):
    stop_session()
    port = Portfolio(capital=capital, cash=capital)
    port.save(DEFAULT_PORTFOLIO_FILE)
    return {"status": "reset", "capital": capital}


@router.get("/status")
def session_status():
    state = get_state()
    mkt = market_status()
    return {
        "status": state.status,
        "symbols": state.symbols,
        "interval": state.interval,
        "capital": state.capital,
        "market_open": mkt["open"],
        "market_reason": mkt["reason"],
    }
