"""Detect candlestick patterns using TA-Lib."""
import talib
import pandas as pd

# Curated set of high-signal patterns for Indian equity markets.
# Maps TA-Lib function name → human-readable label
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


def detect(df: pd.DataFrame, patterns: list[str] | None = None) -> pd.DataFrame:
    """
    Run candlestick pattern detection on OHLCV data.

    Args:
        df:       DataFrame with lowercase columns: open, high, low, close
        patterns: List of TA-Lib pattern keys to detect (e.g. 'CDLHAMMER').
                  Defaults to all patterns in PATTERNS.

    Returns:
        DataFrame with columns: date, pattern, signal, value, candle, strength
        Only rows where a pattern fired (value != 0) are returned.
    """
    targets = patterns if patterns is not None else list(PATTERNS.keys())

    open_ = df["open"].astype(float)
    high  = df["high"].astype(float)
    low   = df["low"].astype(float)
    close = df["close"].astype(float)

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
            results.append({
                "date":     date,
                "pattern":  pat_name,
                "signal":   signal,
                "value":    val,
                "candle":   colour,
                "strength": strength,
            })

    if not results:
        return pd.DataFrame(columns=["date", "pattern", "signal", "value", "candle", "strength"])

    return pd.DataFrame(results).sort_values("date").reset_index(drop=True)


def detect_latest(df: pd.DataFrame, patterns: list[str] | None = None) -> pd.DataFrame:
    """Return only patterns detected on the most recent candle."""
    all_signals = detect(df, patterns)
    if all_signals.empty:
        return all_signals
    latest_date = all_signals["date"].max()
    return all_signals[all_signals["date"] == latest_date].reset_index(drop=True)
