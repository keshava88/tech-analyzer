"""Global session state shared between the FastAPI routers and the session thread."""
import asyncio
import threading
from dataclasses import dataclass, field
from enum import Enum


class SessionStatus(str, Enum):
    IDLE         = "idle"
    RUNNING      = "running"
    STOPPED      = "stopped"
    EOD_COMPLETE = "eod_complete"


@dataclass
class AppState:
    status: SessionStatus = SessionStatus.IDLE
    session: object = None                        # PaperSession | None
    thread: threading.Thread | None = None
    event_queue: asyncio.Queue | None = None      # set by app lifespan
    symbols: list[str] = field(default_factory=list)
    interval: str = "15m"
    capital: float = 100_000.0


_state = AppState()


def get_state() -> AppState:
    return _state
