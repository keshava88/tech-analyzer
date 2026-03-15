"""Generate candlestick charts with pattern highlights using mplfinance."""
from pathlib import Path

import numpy as np
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt


def _draw_sr(ax, levels: dict, price_min: float, price_max: float) -> None:
    """Draw support/resistance lines on a mplfinance price axis."""
    from tech_analyzer.analysis.sr_levels import levels_in_range

    visible = levels_in_range(levels, price_min, price_max)

    for lvl in visible["support"]:
        p = lvl["price"]
        ax.axhline(p, color="#007a00", linestyle="--", linewidth=0.8, alpha=0.65)
        ax.annotate(
            f"S {p:.1f}",
            xy=(1.01, p), xycoords=("axes fraction", "data"),
            fontsize=7, color="#007a00", va="center",
        )

    for lvl in visible["resistance"]:
        p = lvl["price"]
        ax.axhline(p, color="#cc0000", linestyle="--", linewidth=0.8, alpha=0.65)
        ax.annotate(
            f"R {p:.1f}",
            xy=(1.01, p), xycoords=("axes fraction", "data"),
            fontsize=7, color="#cc0000", va="center",
        )


def plot_signal(
    df: pd.DataFrame,
    signal: dict,
    window: int = 5,
    save_dir: str = "output/charts",
    show_sr: bool = False,
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
    trend      = signal.get("trend", "")

    # Locate the pattern candle in the DataFrame
    try:
        idx = df.index.get_loc(pat_date)
    except KeyError:
        idx = df.index.searchsorted(pat_date)

    start = max(0, idx - window)
    end   = min(len(df), idx + window + 1)
    slice_df = df.iloc[start:end].copy()

    # Compute EMAs on full df so values are accurate at the window edges
    close_full = df["close"].astype(float)
    ema20 = close_full.ewm(span=20, adjust=False).mean().iloc[start:end]
    ema50 = close_full.ewm(span=50, adjust=False).mean().iloc[start:end]

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

    addplots = [
        mpf.make_addplot(marker_prices, type="scatter", markersize=120,
                         marker=marker_shape, color=marker_color),
        mpf.make_addplot(ema20, color="#1f77b4", width=1.2, label="EMA 20"),
        mpf.make_addplot(ema50, color="#ff7f0e", width=1.2, label="EMA 50"),
    ]

    # Title: pattern + signal + date
    date_str = pd.Timestamp(pat_date).strftime("%Y-%m-%d")
    title = f"{pat_name}  |  {pat_signal.upper()}  |  {date_str}"

    # Subtitle: candle colour, strength, trend
    candle_colour_hex = "#00b300" if candle == "green" else "#cc0000"
    parts = [f"Candle: {candle.upper()}"]
    if strength != "-":
        parts.append(f"Strength: {strength.upper()}")
    if trend:
        parts.append(f"Trend: {trend.upper()}")
    annotation = "  |  ".join(parts)

    # Action calls
    if_flat    = signal.get("if_flat", "")
    if_flat_ls = signal.get("if_flat_ls", "")
    if_long    = signal.get("if_long", "")

    # File path
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    safe_name = pat_name.replace(" ", "_").replace("/", "-")
    fname = f"{save_dir}/{date_str}_{safe_name}_{pat_signal}.png"

    fig, axes = mpf.plot(
        slice_df,
        type="candle",
        style="yahoo",
        title=title,
        ylabel="Price (INR)",
        volume=True,
        addplot=addplots,
        returnfig=True,
    )

    # EMA legend — use handles registered by make_addplot label= param
    price_ax = axes[0]
    handles, labels = price_ax.get_legend_handles_labels()
    if handles:
        price_ax.legend(handles, labels, loc="upper left", fontsize=8, framealpha=0.7)

    # S/R lines
    if show_sr:
        from tech_analyzer.analysis.sr_levels import find_levels
        sr = find_levels(df)
        price_min = slice_df["Low"].min()
        price_max = slice_df["High"].max()
        _draw_sr(price_ax, sr, float(price_min), float(price_max))

    # Subtitle annotation: candle / strength / trend
    fig.text(
        0.5, 0.91,
        annotation,
        ha="center", va="top",
        fontsize=9, color=candle_colour_hex, fontstyle="italic",
    )

    # Action boxes: three labelled badges at the bottom of the figure
    if if_flat:
        def _action_colors(call: str) -> tuple[str, str]:
            """Return (text_color, box_color) for a trade call."""
            if call == "BUY" or call == "BUY MORE":
                return "#ffffff", "#007a00"
            if call == "SELL":
                return "#ffffff", "#cc0000"
            return "#333333", "#dddddd"   # WAIT / HOLD

        actions = [
            ("No Position\n(Long Only)", if_flat),
            ("No Position\n(Long/Short)", if_flat_ls),
            ("Holding\nLong", if_long),
        ]
        box_y = 0.04
        xs = [0.22, 0.50, 0.78]
        for x, (label, call) in zip(xs, actions):
            txt_col, bg_col = _action_colors(call)
            fig.text(
                x, box_y, f"{label}\n{call}",
                ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=txt_col,
                bbox=dict(boxstyle="round,pad=0.4", facecolor=bg_col, edgecolor="none"),
            )

    fig.savefig(fname, dpi=120, bbox_inches="tight")
    plt.close(fig)

    return fname


def plot_all_signals(
    df: pd.DataFrame,
    signals: pd.DataFrame,
    window: int = 5,
    save_dir: str = "output/charts",
    show_sr: bool = False,
) -> list[str]:
    """Generate charts for all signals. Returns list of saved file paths."""
    if signals.empty:
        return []

    saved = []
    for _, row in signals.iterrows():
        path = plot_signal(df, row.to_dict(), window=window, save_dir=save_dir, show_sr=show_sr)
        saved.append(path)
        print(f"  Saved: {path}")

    return saved
