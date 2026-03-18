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


def setup(level: int = logging.INFO) -> None:
    """Configure the root tech_analyzer logger. Safe to call multiple times."""
    logger = logging.getLogger("tech_analyzer")
    if logger.handlers:
        return  # already configured

    handler = logging.StreamHandler()
    handler.setFormatter(
        _ISTFormatter(
            fmt="[%(asctime)s] %(levelname)-8s %(message)s",
            datefmt="%H:%M:%S IST",
        )
    )
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
