"""Detect support and resistance levels from OHLCV data using swing highs/lows."""
import pandas as pd


def _merge_levels(prices: list[float], merge_pct: float) -> list[dict]:
    """
    Merge nearby price levels into clusters.

    Returns list of {"price": float, "touches": int} sorted ascending.
    """
    if not prices:
        return []
    prices = sorted(prices)
    clusters: list[dict] = []
    cluster = [prices[0]]
    for p in prices[1:]:
        if (p - cluster[0]) / cluster[0] * 100 <= merge_pct:
            cluster.append(p)
        else:
            clusters.append({"price": sum(cluster) / len(cluster), "touches": len(cluster)})
            cluster = [p]
    clusters.append({"price": sum(cluster) / len(cluster), "touches": len(cluster)})
    return clusters


def find_levels(
    df: pd.DataFrame,
    left: int = 5,
    right: int = 5,
    merge_pct: float = 0.5,
) -> dict[str, list[dict]]:
    """
    Detect support and resistance levels from OHLCV data.

    A swing high at index i: high[i] is the maximum over [i-left, i+right].
    A swing low at index i:  low[i]  is the minimum over [i-left, i+right].
    Nearby levels (within merge_pct %) are merged into a single cluster.

    Args:
        df:        OHLCV DataFrame (lowercase columns, DatetimeIndex)
        left:      Candles to the left required for a swing confirmation
        right:     Candles to the right required for a swing confirmation
        merge_pct: Levels within this % of each other are merged (default 0.5%)

    Returns:
        {"support": [...], "resistance": [...]}
        Each item: {"price": float, "touches": int}
        Sorted by price ascending.
    """
    highs = df["high"].astype(float).values
    lows  = df["low"].astype(float).values
    n = len(df)

    swing_highs: list[float] = []
    swing_lows:  list[float] = []

    for i in range(left, n - right):
        window_high = highs[i - left: i + right + 1]
        window_low  = lows[i - left:  i + right + 1]
        if highs[i] == window_high.max():
            swing_highs.append(float(highs[i]))
        if lows[i] == window_low.min():
            swing_lows.append(float(lows[i]))

    return {
        "support":    _merge_levels(swing_lows,  merge_pct),
        "resistance": _merge_levels(swing_highs, merge_pct),
    }


def levels_in_range(
    levels: dict[str, list[dict]],
    price_min: float,
    price_max: float,
    padding_pct: float = 2.0,
) -> dict[str, list[dict]]:
    """
    Filter levels to those visible within a price range.

    Adds a padding_pct % buffer above and below the range.
    """
    pad = (price_max - price_min) * padding_pct / 100
    lo = price_min - pad
    hi = price_max + pad
    return {
        "support":    [l for l in levels["support"]    if lo <= l["price"] <= hi],
        "resistance": [l for l in levels["resistance"] if lo <= l["price"] <= hi],
    }
