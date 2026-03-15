"""
Paper trading engine — processes each new candle, manages exits and entries.

Trade lifecycle:
    1. On each new candle close, check exits for all open positions.
    2. Detect candlestick signals on the new candle.
    3. Open new positions for aligned signals (one per symbol).

Exit triggers (checked in priority order):
    1. Target hit   — price reached target_price
    2. Stoploss hit — price breached stoploss_price
    3. Opposite signal — a new signal in the opposite direction closes the trade
    4. End of day   — all positions closed at EOD close price

Position sizing:
    auto: floor(capital * risk_pct / entry_price)   [default 10% of capital per trade]
    fixed: --units N shares
"""
from datetime import datetime

from tech_analyzer.trading.portfolio import Portfolio, Position


def _calc_targets(
    entry: float,
    signal: str,
    target_pct: float,
    stoploss_pct: float,
) -> tuple[float, float]:
    """Return (target_price, stoploss_price) for a trade."""
    if signal == "bullish":
        target = entry * (1 + target_pct / 100)
        stop   = entry * (1 - stoploss_pct / 100)
    else:
        target = entry * (1 - target_pct / 100)
        stop   = entry * (1 + stoploss_pct / 100)
    return round(target, 2), round(stop, 2)


def _units_for(
    capital: float,
    entry: float,
    fixed_units: int | None,
    risk_pct: float = 10.0,
) -> int:
    if fixed_units:
        return fixed_units
    units = int(capital * risk_pct / 100 / entry)
    return max(units, 1)


def _check_exit(
    pos: Position,
    candle_high: float,
    candle_low: float,
    candle_close: float,
    candle_date: str,
    eod: bool,
    new_signal: str | None,
) -> tuple[bool, float, str]:
    """
    Check whether a position should be closed.
    Returns (should_close, exit_price, reason).
    """
    if eod:
        return True, candle_close, "eod"

    if pos.signal == "bullish":
        if candle_high >= pos.target_price:
            return True, pos.target_price, "target"
        if candle_low <= pos.stoploss_price:
            return True, pos.stoploss_price, "stoploss"
        if new_signal == "bearish":
            return True, candle_close, "signal"
    else:  # short
        if candle_low <= pos.target_price:
            return True, pos.target_price, "target"
        if candle_high >= pos.stoploss_price:
            return True, pos.stoploss_price, "stoploss"
        if new_signal == "bullish":
            return True, candle_close, "signal"

    return False, candle_close, ""


def process_candle(
    portfolio: Portfolio,
    symbol: str,
    candle: dict,            # {date, open, high, low, close, ...}
    signals_df,              # detect() output — may be empty
    target_pct: float = 2.0,
    stoploss_pct: float = 1.0,
    fixed_units: int | None = None,
    eod: bool = False,
) -> list[dict]:
    """
    Process one new candle close for a symbol.

    Returns a list of event dicts (one per open/close action) for logging:
        {"event": "open"|"close", "symbol", "pattern", "signal",
         "price", "units", "reason"?, "pnl"?}
    """
    events = []
    date_str = str(candle["date"])
    close = float(candle["close"])
    high  = float(candle["high"])
    low   = float(candle["low"])

    # Pull the latest signal for this symbol from signals_df (if any)
    if not signals_df.empty and "date" in signals_df.columns:
        latest = signals_df[signals_df["date"] == candle["date"]]
        # prefer aligned signals; if multiple, take the first
        aligned = latest[latest["aligned"]]
        row = aligned.iloc[0] if not aligned.empty else (latest.iloc[0] if not latest.empty else None)
    else:
        row = None

    new_signal = row["signal"] if row is not None else None

    # --- Check exits ---
    pos = portfolio.position_for(symbol)
    if pos is not None:
        should_close, exit_price, reason = _check_exit(
            pos, high, low, close, date_str, eod, new_signal
        )
        if should_close:
            trade = portfolio.close_position(pos, exit_price, reason, exit_date=date_str)
            events.append({
                "event":   "close",
                "symbol":  symbol,
                "pattern": pos.pattern,
                "signal":  pos.signal,
                "price":   exit_price,
                "units":   pos.units,
                "reason":  reason,
                "pnl":     trade.pnl,
                "pct":     trade.pct,
            })
            pos = None  # position is now closed

    # --- Check entries (only if no open position and not EOD) ---
    if pos is None and not eod and row is not None:
        units = _units_for(portfolio.capital, close, fixed_units)
        target, stop = _calc_targets(close, new_signal, target_pct, stoploss_pct)

        position = Position(
            symbol=symbol,
            entry_date=date_str,
            entry_price=close,
            units=units,
            signal=new_signal,
            pattern=row["pattern"],
            target_price=target,
            stoploss_price=stop,
        )
        opened = portfolio.open_position(position)
        if opened:
            events.append({
                "event":   "open",
                "symbol":  symbol,
                "pattern": row["pattern"],
                "signal":  new_signal,
                "price":   close,
                "units":   units,
                "target":  target,
                "stop":    stop,
            })

    return events
