"""Runs PaperSession in a background thread and bridges events to asyncio."""
import asyncio
import logging
import threading
from datetime import datetime, timezone

from tech_analyzer.trading.session import PaperSession
from tech_analyzer.trading.portfolio import DEFAULT_PORTFOLIO_FILE
from tech_analyzer.web.state import get_state, SessionStatus

log = logging.getLogger(__name__)


def _make_callback(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):
    def on_event(event: dict) -> None:
        event.setdefault("ts", datetime.now(tz=timezone.utc).isoformat())
        asyncio.run_coroutine_threadsafe(queue.put(event), loop)
    return on_event


def start_session(config: dict) -> None:
    state = get_state()
    if state.status == SessionStatus.RUNNING:
        raise RuntimeError("Session already running.")

    loop = asyncio.get_event_loop()
    callback = _make_callback(loop, state.event_queue)

    session = PaperSession(
        symbols=config["symbols"],
        interval=config["interval"],
        capital=config["capital"],
        target_pct=config["target_pct"],
        stoploss_pct=config["stoploss_pct"],
        fixed_units=config.get("fixed_units"),
        patterns=config.get("patterns"),
        trend_filter=config.get("trend_filter", True),
        fresh=config.get("fresh", False),
        on_event=callback,
    )

    state.session = session
    state.symbols = config["symbols"]
    state.interval = config["interval"]
    state.capital = config["capital"]
    state.status = SessionStatus.RUNNING

    def _run():
        try:
            session.run()
        except Exception as e:
            log.error("Session crashed: %s", e)
        finally:
            state.status = SessionStatus.STOPPED
            state.session = None
            state.thread = None
            asyncio.run_coroutine_threadsafe(
                state.event_queue.put({"type": "session_status", "status": "stopped"}),
                loop,
            )

    thread = threading.Thread(target=_run, daemon=True, name="paper-session")
    state.thread = thread
    thread.start()


def stop_session() -> None:
    state = get_state()
    if state.session is not None:
        state.session._stop_requested = True
