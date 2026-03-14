"""Detect candlestick patterns using pandas-ta."""
import pandas as pd
import pandas_ta as ta

# Curated set of high-signal patterns relevant for Indian equity markets.
# Values indicate signal direction: +1 = bullish, -1 = bearish, 0 = neutral/context-dependent
PATTERNS = {
    # Single candle
    "doji":           0,
    "dragonflydoji":  1,
    "gravestonedoji": -1,
    "hammer":         1,
    "hangingman":     -1,
    "invertedhammer": 1,
    "shootingstar":   -1,
    "marubozu":       0,   # direction depends on colour
    "spinningtop":    0,

    # Two candle
    "engulfing":      0,   # CDL returns +100 (bull) or -100 (bear)
    "harami":         0,
    "haramicross":    0,
    "inside":         0,
    "piercing":       1,
    "darkcloudcover": -1,

    # Three candle
    "morningstar":        1,
    "eveningstar":        -1,
    "morningdojistar":    1,
    "eveningdojistar":    -1,
    "3whitesoldiers":     1,
    "3blackcrows":        -1,
    "3inside":            0,
    "3outside":           0,
}


def detect(df: pd.DataFrame, patterns: list[str] | None = None) -> pd.DataFrame:
    """
    Run candlestick pattern detection on OHLCV data.

    Args:
        df:       DataFrame with lowercase columns: open, high, low, close, volume
        patterns: List of pattern names to detect. Defaults to all patterns in PATTERNS.

    Returns:
        DataFrame of detected signals with columns:
            date, pattern, signal (bullish/bearish/neutral), value
        Only rows where a pattern fired (value != 0) are returned.
    """
    targets = patterns if patterns is not None else list(PATTERNS.keys())
    results = []

    for name in targets:
        if name not in PATTERNS:
            raise ValueError(f"Unknown pattern '{name}'. Available: {list(PATTERNS.keys())}")

        try:
            result = df.ta.cdl_pattern(name=name)
        except Exception:
            continue  # skip patterns unsupported by current pandas-ta version

        if result is None or result.empty:
            continue

        # pandas-ta returns a DataFrame with one column named e.g. 'CDL_DOJI_10_0.1'
        col = result.columns[0]
        fired = result[result[col] != 0]

        for date, row in fired.iterrows():
            val = int(row[col])
            signal = "bullish" if val > 0 else "bearish" if val < 0 else "neutral"
            results.append({"date": date, "pattern": name, "signal": signal, "value": val})

    if not results:
        return pd.DataFrame(columns=["date", "pattern", "signal", "value"])

    out = pd.DataFrame(results).sort_values("date").reset_index(drop=True)
    return out


def detect_latest(df: pd.DataFrame, patterns: list[str] | None = None) -> pd.DataFrame:
    """
    Return only patterns detected on the most recent candle.
    Useful for live screening.
    """
    all_signals = detect(df, patterns)
    if all_signals.empty:
        return all_signals
    latest_date = all_signals["date"].max()
    return all_signals[all_signals["date"] == latest_date].reset_index(drop=True)
