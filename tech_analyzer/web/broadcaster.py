"""Fan-out WebSocket broadcaster — drains asyncio.Queue → all connected clients."""
import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)

_clients: set[WebSocket] = set()


async def register(ws: WebSocket) -> None:
    _clients.add(ws)
    log.debug("WS client connected (%d total)", len(_clients))


async def unregister(ws: WebSocket) -> None:
    _clients.discard(ws)
    log.debug("WS client disconnected (%d total)", len(_clients))


async def broadcast(message: dict) -> None:
    dead: set[WebSocket] = set()
    for ws in _clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    _clients -= dead


async def queue_consumer(queue: asyncio.Queue) -> None:
    """Background task: drain the event queue and broadcast to all WS clients."""
    while True:
        event = await queue.get()
        await broadcast(event)
