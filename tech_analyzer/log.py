"""
Centralised logging configuration for tech-analyzer.

All modules use logging.getLogger(__name__).
Call tech_analyzer.log.setup() once at startup (done in cli.main).

Format: [HH:MM:SS IST] LEVEL  message
Timestamps are always in IST regardless of system timezone.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")


class _ISTFormatter(logging.Formatter):
    """Logging formatter that renders timestamps in IST."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=_IST)
        return dt.strftime(datefmt or "%H:%M:%S")


_FMT = "[%(asctime)s] %(levelname)-8s %(message)s"
_DATEFMT = "%H:%M:%S IST"


def _make_handler() -> logging.StreamHandler:
    h = logging.StreamHandler()
    h.setFormatter(_ISTFormatter(fmt=_FMT, datefmt=_DATEFMT))
    return h


def setup(level: int = logging.INFO) -> None:
    """
    Configure IST timestamps on all relevant loggers:
      - tech_analyzer.*  (application logs)
      - uvicorn, uvicorn.error, uvicorn.access  (server access/error logs)

    Safe to call multiple times.
    """
    for name in ("tech_analyzer", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        if logger.handlers:
            # Replace existing handlers' formatters rather than adding new ones
            for h in logger.handlers:
                h.setFormatter(_ISTFormatter(fmt=_FMT, datefmt=_DATEFMT))
        else:
            logger.addHandler(_make_handler())
        logger.setLevel(level)
        logger.propagate = False
