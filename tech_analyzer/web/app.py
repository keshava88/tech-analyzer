"""FastAPI application factory."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from tech_analyzer.web.state import get_state, SessionStatus
from tech_analyzer.web.broadcaster import queue_consumer, broadcast
from tech_analyzer.web.routers import session_router, portfolio_router, ws_router

log = logging.getLogger(__name__)

_DIST = Path(__file__).parent.parent.parent / "web" / "dist"


async def _ltp_poll_loop() -> None:
    """Poll LTP every 5 seconds during an active session and broadcast."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from tech_analyzer.data.live import fetch_ltp

    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ltp-poll")
    state = get_state()

    while True:
        await asyncio.sleep(5)
        if state.status != SessionStatus.RUNNING or not state.symbols:
            continue
        try:
            loop = asyncio.get_event_loop()
            prices = await loop.run_in_executor(executor, fetch_ltp, state.symbols)
            if prices:
                await broadcast({"type": "ltp_tick", "prices": prices})
        except Exception as e:
            log.debug("LTP poll error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from tech_analyzer.log import setup as _setup_logging
    _setup_logging()

    state = get_state()
    state.event_queue = asyncio.Queue()

    consumer = asyncio.create_task(queue_consumer(state.event_queue))
    ltp_task  = asyncio.create_task(_ltp_poll_loop())

    yield

    consumer.cancel()
    ltp_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="Tech Analyzer — Paper Trading", version="1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(session_router.router, prefix="/api")
    app.include_router(portfolio_router.router, prefix="/api")
    app.include_router(ws_router.router)

    # Serve built React app (only if dist exists)
    if _DIST.exists():
        app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")

    return app


app = create_app()
