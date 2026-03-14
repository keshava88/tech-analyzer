"""Detect candlestick patterns using TA-Lib."""
import talib
import pandas as pd

# Curated set of high-signal patterns for Indian equity markets.
# Maps TA-Lib function name -> human-readable label
PATTERNS: dict[str, str] = {
    # Single candle
    "CDLDOJI":           "Doji",
    "CDLDRAGONFLYDOJI":  "Dragonfly Doji",
    "CDLGRAVESTONEDOJI": "Gravestone Doji",
    "CDLHAMMER":         "Hammer",
    "CDLHANGINGMAN":     "Hanging Man",
    "CDLINVERTEDHAMMER": "Inverted Hammer",
    "CDLSHOOTINGSTAR":   "Shooting Star",
    "CDLMARUBOZU":       "Marubozu",
    "CDLSPINNINGTOP":    "Spinning Top",

    # Two candle
    "CDLENGULFING":      "Engulfing",
    "CDLHARAMI":         "Harami",
    "CDLHARAMICROSS":    "Harami Cross",
    "CDLPIERCING":       "Piercing Line",
    "CDLDARKCLOUDCOVER": "Dark Cloud Cover",

    # Three candle
    "CDLMORNINGSTAR":      "Morning Star",
    "CDLEVENINGSTAR":      "Evening Star",
    "CDLMORNINGDOJISTAR":  "Morning Doji Star",
    "CDLEVENINGDOJISTAR":  "Evening Doji Star",
    "CDL3WHITESOLDIERS":   "Three White Soldiers",
    "CDL3BLACKCROWS":      "Three Black Crows",
    "CDL3INSIDE":          "Three Inside Up/Down",
    "CDL3OUTSIDE":         "Three Outside Up/Down",
}

# Patterns where candle colour affects signal strength
# bullish pattern: green body = strong, red body = weak
# bearish pattern: red body = strong, green body = weak
COLOUR_SENSITIVE = {
    "Hammer", "Inverted Hammer", "Hanging Man", "Shooting Star",
    "Engulfing", "Marubozu", "Piercing Line", "Dark Cloud Cover",
    "Morning Star", "Evening Star", "Morning Doji Star", "Evening Doji Star",
    "Three White Soldiers", "Three Black Crows",
}

# Reversal patterns: bullish reversal is meaningful at the bottom of a downtrend,
# bearish reversal at the top of an uptrend.
REVERSAL_PATTERNS = {
    "Hammer", "Inverted Hammer", "Hanging Man", "Shooting Star",
    "Dragonfly Doji", "Gravestone Doji",
    "Engulfing", "Harami", "Harami Cross", "Piercing Line", "Dark Cloud Cover",
    "Morning Star", "Evening Star", "Morning Doji Star", "Evening Doji Star",
    "Three Inside Up/Down", "Three Outside Up/Down",
}

# Continuation patterns: bullish continuation meaningful in uptrend, bearish in downtrend.
CONTINUATION_PATTERNS = {
    "Three White Soldiers", "Three Black Crows", "Marubozu",
}
# Note: Doji and Spinning Top are pure indecision — no directional alignment defined.


def _candle_colour(row: pd.Series) -> str:
    return "green" if row["close"] >= row["open"] else "red"


def _strength(signal: str, colour: str, pattern: str) -> str:
    """Return 'strong' or 'weak' based on signal direction vs candle colour."""
    if pattern not in COLOUR_SENSITIVE:
        return "-"
    if signal == "bullish":
        return "strong" if colour == "green" else "weak"
    else:
        return "strong" if colour == "red" else "weak"


def classify_trend(close: pd.Series, fast: int = 20, slow: int = 50) -> pd.Series:
    """
    Classify trend per candle using EMA crossover.

    Returns a Series with values: 'uptrend', 'downtrend', or 'sideways'.
    - uptrend:   EMA(fast) > EMA(slow)
    - downtrend: EMA(fast) < EMA(slow)
    - sideways:  insufficient data (NaN period at start)
    """
    ema_fast = talib.EMA(close.astype(float), timeperiod=fast)
    ema_slow = talib.EMA(close.astype(float), timeperiod=slow)

    trend = pd.Series("sideways", index=close.index, dtype=object)
    trend[ema_fast > ema_slow] = "uptrend"
    trend[ema_fast < ema_slow] = "downtrend"
    trend[ema_fast.isna() | ema_slow.isna()] = "sideways"
    return trend


def _trade_actions(signal: str, aligned: bool) -> tuple[str, str, str]:
    """
    Return (if_flat, if_flat_ls, if_long) standardised action strings.

    if_flat    — long-only trader with no position  (BUY / WAIT / HOLD)
    if_flat_ls — long-short trader with no position (BUY / SELL / HOLD)
    if_long    — trader holding a long position     (BUY MORE / SELL / HOLD)
    """
    if not aligned:
        return "HOLD", "HOLD", "HOLD"
    if signal == "bullish":
        return "BUY", "BUY", "BUY MORE"
    else:  # bearish
        return "WAIT", "SELL", "SELL"


def _is_aligned(signal: str, pattern: str, trend: str) -> bool:
    """Return True if the pattern makes sense given the prevailing trend."""
    if trend == "sideways":
        return False
    if pattern in REVERSAL_PATTERNS:
        # bullish reversal at bottom of downtrend, bearish reversal at top of uptrend
        return (signal == "bullish" and trend == "downtrend") or \
               (signal == "bearish" and trend == "uptrend")
    if pattern in CONTINUATION_PATTERNS:
        return (signal == "bullish" and trend == "uptrend") or \
               (signal == "bearish" and trend == "downtrend")
    return False  # Doji, Spinning Top — indecision, no directional alignment


def detect(
    df: pd.DataFrame,
    patterns: list[str] | None = None,
    trend_filter: bool = False,
) -> pd.DataFrame:
    """
    Run candlestick pattern detection on OHLCV data.

    Args:
        df:           DataFrame with lowercase columns: open, high, low, close
        patterns:     List of TA-Lib pattern keys to detect (e.g. 'CDLHAMMER').
                      Defaults to all patterns in PATTERNS.
        trend_filter: If True, return only signals aligned with the prevailing trend.

    Returns:
        DataFrame with columns: date, pattern, signal, value, candle, strength, trend, aligned
        Only rows where a pattern fired (value != 0) are returned.
    """
    targets = patterns if patterns is not None else list(PATTERNS.keys())

    open_ = df["open"].astype(float)
    high  = df["high"].astype(float)
    low   = df["low"].astype(float)
    close = df["close"].astype(float)

    trend_series = classify_trend(close)

    results = []
    for key in targets:
        if key not in PATTERNS:
            raise ValueError(f"Unknown pattern '{key}'. Available: {list(PATTERNS.keys())}")

        fn = getattr(talib, key, None)
        if fn is None:
            continue

        result = fn(open_, high, low, close)
        fired = result[result != 0]

        for date, val in fired.items():
            val = int(val)
            signal = "bullish" if val > 0 else "bearish"
            pat_name = PATTERNS[key]
            colour = _candle_colour(df.loc[date])
            strength = _strength(signal, colour, pat_name)
            trend = trend_series.loc[date]
            aligned = _is_aligned(signal, pat_name, trend)
            if_flat, if_flat_ls, if_long = _trade_actions(signal, aligned)
            results.append({
                "date":       date,
                "pattern":    pat_name,
                "signal":     signal,
                "value":      val,
                "candle":     colour,
                "strength":   strength,
                "trend":      trend,
                "aligned":    aligned,
                "if_flat":    if_flat,
                "if_flat_ls": if_flat_ls,
                "if_long":    if_long,
            })

    cols = ["date", "pattern", "signal", "value", "candle", "strength", "trend", "aligned",
            "if_flat", "if_flat_ls", "if_long"]
    if not results:
        return pd.DataFrame(columns=cols)

    out = pd.DataFrame(results).sort_values("date").reset_index(drop=True)
    if trend_filter:
        out = out[out["aligned"]].reset_index(drop=True)
    return out


def detect_latest(
    df: pd.DataFrame,
    patterns: list[str] | None = None,
    trend_filter: bool = False,
) -> pd.DataFrame:
    """Return only patterns detected on the most recent candle."""
    all_signals = detect(df, patterns, trend_filter=trend_filter)
    if all_signals.empty:
        return all_signals
    latest_date = all_signals["date"].max()
    return all_signals[all_signals["date"] == latest_date].reset_index(drop=True)
