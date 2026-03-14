"""Generate candlestick charts with pattern highlights using mplfinance."""
from pathlib import Path

import numpy as np
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt


def plot_signal(
    df: pd.DataFrame,
    signal: dict,
    window: int = 5,
    save_dir: str = "charts",
) -> str:
    """
    Plot a candlestick chart for a single detected pattern signal.

    Shows `window` candles before and after the pattern candle.
    The pattern candle is highlighted with a coloured triangle marker.
    Candle colour and strength are shown as an annotation on the chart.

    Args:
        df:       Full OHLCV DataFrame (lowercase columns, DatetimeIndex)
        signal:   A single row from detector.detect() as a dict
                  (keys: date, pattern, signal, value, candle, strength)
        window:   Number of candles to show before and after the pattern
        save_dir: Directory to save the PNG file

    Returns:
        Path to the saved PNG file.
    """
    pat_date   = signal["date"]
    pat_name   = signal["pattern"]
    pat_signal = signal["signal"]
    candle     = signal.get("candle", "-")
    strength   = signal.get("strength", "-")

    # Locate the pattern candle in the DataFrame
    try:
        idx = df.index.get_loc(pat_date)
    except KeyError:
        idx = df.index.searchsorted(pat_date)

    start = max(0, idx - window)
    end   = min(len(df), idx + window + 1)
    slice_df = df.iloc[start:end].copy()

    # mplfinance requires capitalised column names
    slice_df = slice_df.rename(columns={
        "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume",
    })

    # Marker: triangle below candle (bullish) or above (bearish)
    marker_prices = pd.Series(np.nan, index=slice_df.index)
    pat_idx_in_slice = idx - start

    if pat_signal == "bullish":
        marker_prices.iloc[pat_idx_in_slice] = slice_df["Low"].iloc[pat_idx_in_slice] * 0.988
        marker_color = "#00b300"
        marker_shape = "^"
    else:
        marker_prices.iloc[pat_idx_in_slice] = slice_df["High"].iloc[pat_idx_in_slice] * 1.012
        marker_color = "#cc0000"
        marker_shape = "v"

    addplot = mpf.make_addplot(
        marker_prices,
        type="scatter",
        markersize=120,
        marker=marker_shape,
        color=marker_color,
    )

    # Title line 1: pattern + signal + date
    date_str = pd.Timestamp(pat_date).strftime("%Y-%m-%d")
    title = f"{pat_name}  ·  {pat_signal.upper()}  ·  {date_str}"

    # Annotation text: candle colour + strength indicator
    candle_colour_hex = "#00b300" if candle == "green" else "#cc0000"
    if strength == "-":
        annotation = f"Candle: {candle.upper()}"
    else:
        annotation = f"Candle: {candle.upper()}  |  Strength: {strength.upper()}"

    # File path
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    safe_name = pat_name.replace(" ", "_").replace("/", "-")
    fname = f"{save_dir}/{date_str}_{safe_name}_{pat_signal}.png"

    fig, axes = mpf.plot(
        slice_df,
        type="candle",
        style="yahoo",
        title=title,
        ylabel="Price (₹)",
        volume=True,
        addplot=[addplot],
        returnfig=True,
    )

    # Add candle colour + strength annotation below the title
    fig.text(
        0.5, 0.91,
        annotation,
        ha="center",
        va="top",
        fontsize=9,
        color=candle_colour_hex,
        fontstyle="italic",
    )

    fig.savefig(fname, dpi=120, bbox_inches="tight")
    plt.close(fig)

    return fname


def plot_all_signals(
    df: pd.DataFrame,
    signals: pd.DataFrame,
    window: int = 5,
    save_dir: str = "charts",
) -> list[str]:
    """Generate charts for all signals. Returns list of saved file paths."""
    if signals.empty:
        return []

    saved = []
    for _, row in signals.iterrows():
        path = plot_signal(df, row.to_dict(), window=window, save_dir=save_dir)
        saved.append(path)
        print(f"  Saved: {path}")

    return saved
