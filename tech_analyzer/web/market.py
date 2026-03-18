"""NSE market-hours helper."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")

# NSE regular session: 09:15 – 15:30 IST, Monday–Friday
_OPEN  = time(9, 15)
_CLOSE = time(15, 30)


def market_status() -> dict:
    """Return {'open': bool, 'reason': str} for the current moment."""
    now = datetime.now(tz=_IST)
    weekday = now.weekday()          # 0=Mon … 6=Sun
    t = now.time()

    if weekday >= 5:
        return {"open": False, "reason": "Weekend"}
    if t < _OPEN:
        opens_in = _minutes_until(_OPEN, t)
        return {"open": False, "reason": f"Pre-market — opens in {opens_in} min"}
    if t >= _CLOSE:
        return {"open": False, "reason": "Market closed (post 15:30)"}

    closes_in = _minutes_until(_CLOSE, t)
    return {"open": True, "reason": f"Market open — closes in {closes_in} min"}


def _minutes_until(target: time, now: time) -> int:
    t_min = target.hour * 60 + target.minute
    n_min = now.hour * 60 + now.minute
    return max(0, t_min - n_min)
