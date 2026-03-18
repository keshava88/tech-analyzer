"""WebSocket endpoint — streams all session events to connected clients."""
import asyncio
from dataclasses import asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from tech_analyzer.web.broadcaster import register, unregister
from tech_analyzer.web.state import get_state
from tech_analyzer.trading.portfolio import Portfolio, DEFAULT_PORTFOLIO_FILE

router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    await register(ws)

    # Send current state immediately on connect
    state = get_state()
    await ws.send_json({"type": "session_status", "status": state.status,
                        "symbols": state.symbols, "interval": state.interval,
                        "capital": state.capital})

    port = Portfolio.load(DEFAULT_PORTFOLIO_FILE)
    await ws.send_json({"type": "portfolio_update",
                        "summary": port.summary(),
                        "positions": [asdict(p) for p in port.positions]})
    try:
        while True:
            # Keep alive — client can send pings; we just discard them
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await unregister(ws)
