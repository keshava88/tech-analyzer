"""
End-of-day report generator.

For each symbol traded today:
  - Candlestick chart with entry/exit markers, target/stop lines, EMA20/50
  - Per-instrument P&L table printed to log

Charts saved to: output/paper_trading/YYYY-MM-DD/
"""
import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from tech_analyzer.trading.portfolio import ClosedTrade, Portfolio

log = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
_TODAY = date.today().isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today_trades(portfolio: Portfolio) -> list[ClosedTrade]:
    """Return closed trades where entry OR exit was today."""
    return [
        t for t in portfolio.closed_trades
        if t.entry_date[:10] == _TODAY or t.exit_date[:10] == _TODAY
    ]


def _trades_by_symbol(trades: list[ClosedTrade]) -> dict[str, list[ClosedTrade]]:
    result: dict[str, list[ClosedTrade]] = {}
    for t in trades:
        result.setdefault(t.symbol, []).append(t)
    return result


def _fetch_today_candles(symbol: str, interval: str) -> pd.DataFrame | None:
    """Fetch today's intraday candles for the chart."""
    try:
        from tech_analyzer.data.live import fetch
        df = fetch(symbol, interval=interval)
        # Keep only today's candles
        today_str = _TODAY
        df = df[df.index.date == date.fromisoformat(today_str)]
        return df if not df.empty else None
    except Exception as e:
        log.warning("Could not fetch candles for %s: %s", symbol, e)
        return None


def _to_ts(dt_str: str) -> pd.Timestamp:
    return pd.Timestamp(dt_str)


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def _plot_trade_chart(
    symbol: str,
    df: pd.DataFrame,
    trades: list[ClosedTrade],
    open_positions: list,
    save_dir: Path,
) -> str | None:
    """
    Generate a candlestick chart for one symbol showing all trades today.
    Returns the saved file path, or None on failure.
    """
    if df.empty:
        return None

    plot_df = df.rename(columns={
        "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume",
    })

    close_full = df["close"].astype(float)
    ema20 = close_full.ewm(span=20, adjust=False).mean()
    ema50 = close_full.ewm(span=50, adjust=False).mean()

    # --- Build marker series ---
    entry_long  = pd.Series(np.nan, index=df.index)
    entry_short = pd.Series(np.nan, index=df.index)
    exit_win    = pd.Series(np.nan, index=df.index)
    exit_loss   = pd.Series(np.nan, index=df.index)

    for t in trades:
        entry_ts = _to_ts(t.entry_date)
        exit_ts  = _to_ts(t.exit_date)

        # Snap to nearest candle in index
        def nearest(ts):
            diffs = abs(df.index - ts)
            loc = diffs.argmin()
            return df.index[loc]

        e_idx = nearest(entry_ts)
        x_idx = nearest(exit_ts)

        if t.signal == "bullish":
            entry_long[e_idx]  = df["low"][e_idx]  * 0.990
        else:
            entry_short[e_idx] = df["high"][e_idx] * 1.010

        if t.pnl >= 0:
            exit_win[x_idx]  = df["high"][x_idx] * 1.010
        else:
            exit_loss[x_idx] = df["high"][x_idx] * 1.010

    # Only include marker series that have at least one non-NaN value
    # (mplfinance crashes on all-NaN scatter series)
    addplots = [
        mpf.make_addplot(ema20, color="#1f77b4", width=1.0, label="EMA20"),
        mpf.make_addplot(ema50, color="#ff7f0e", width=1.0, label="EMA50"),
    ]
    def _add_scatter(series, marker, color, label):
        if series.notna().any():
            addplots.append(mpf.make_addplot(series, type="scatter", markersize=140,
                                             marker=marker, color=color, label=label))
    _add_scatter(entry_long,  "^", "#00aa00", "Entry Long")
    _add_scatter(entry_short, "v", "#cc0000", "Entry Short")
    _add_scatter(exit_win,    "*", "#00aa00", "Exit Win")
    _add_scatter(exit_loss,   "x", "#cc0000", "Exit Loss")

    short_name = symbol.replace(".NS", "").replace(".BO", "")
    title = f"{short_name}  |  {_TODAY}  |  {len(trades)} trade(s)"

    fig, axes = mpf.plot(
        plot_df,
        type="candle",
        style="yahoo",
        title=title,
        ylabel="Price (INR)",
        volume=True,
        addplot=addplots,
        returnfig=True,
        figsize=(14, 7),
    )

    price_ax = axes[0]

    # Draw target/stop lines for each trade
    colors = ["#2ca02c", "#d62728", "#9467bd", "#8c564b"]
    for i, t in enumerate(trades):
        c = colors[i % len(colors)]
        entry_ts = _to_ts(t.entry_date)
        exit_ts  = _to_ts(t.exit_date)
        x_start  = df.index.searchsorted(entry_ts)
        x_end    = min(df.index.searchsorted(exit_ts) + 1, len(df) - 1)

        price_ax.hlines(t.target_price, x_start, x_end,
                        colors="#00aa00", linestyles="--", linewidth=0.9, alpha=0.7)
        price_ax.hlines(t.stoploss_price, x_start, x_end,
                        colors="#cc0000", linestyles="--", linewidth=0.9, alpha=0.7)
        price_ax.hlines(t.entry_price, x_start, x_end,
                        colors=c, linestyles=":", linewidth=0.8, alpha=0.6)

    # Legend
    handles, labels = price_ax.get_legend_handles_labels()
    if handles:
        price_ax.legend(handles, labels, loc="upper left", fontsize=7, framealpha=0.7)

    save_dir.mkdir(parents=True, exist_ok=True)
    fname = save_dir / f"{short_name}.png"
    fig.savefig(fname, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return str(fname)


# ---------------------------------------------------------------------------
# P&L statement
# ---------------------------------------------------------------------------

def _log_pnl_statement(trades_by_symbol: dict[str, list[ClosedTrade]]) -> None:
    if not trades_by_symbol:
        log.info("No trades today.")
        return

    log.info("=" * 90)
    log.info("END-OF-DAY P&L STATEMENT  —  %s", _TODAY)
    log.info("=" * 90)
    log.info(
        "  %-20s %-22s %-8s %8s %8s %6s %9s %-10s",
        "Symbol", "Pattern", "Dir", "Entry", "Exit", "Units", "PnL (₹)", "Reason",
    )
    log.info("  %s", "-" * 86)

    total_pnl = 0.0
    total_wins = 0
    total_losses = 0

    for symbol, trades in sorted(trades_by_symbol.items()):
        sym_pnl = sum(t.pnl for t in trades)
        sym_wins = sum(1 for t in trades if t.pnl > 0)
        sym_losses = sum(1 for t in trades if t.pnl <= 0)

        for t in trades:
            sign = "+" if t.pnl >= 0 else ""
            log.info(
                "  %-20s %-22s %-8s %8.2f %8.2f %6d %s%8.2f  %-10s",
                t.symbol, t.pattern, t.signal.upper(),
                t.entry_price, t.exit_price, t.units,
                sign, t.pnl, t.exit_reason,
            )

        sign = "+" if sym_pnl >= 0 else ""
        log.info(
            "  %-20s %-22s %-8s %8s %8s %6s %s%8.2f  [%dW/%dL]",
            f"  → {symbol}", "", "",
            "", "", "", sign, sym_pnl, sym_wins, sym_losses,
        )
        log.info("  %s", "·" * 86)

        total_pnl    += sym_pnl
        total_wins   += sym_wins
        total_losses += sym_losses

    total_trades = total_wins + total_losses
    hit_rate = f"{total_wins / total_trades * 100:.1f}%" if total_trades else "-"
    sign = "+" if total_pnl >= 0 else ""

    log.info("  %s", "=" * 86)
    log.info(
        "  TOTAL  |  Trades: %d  Wins: %d  Losses: %d  Hit Rate: %s  Net P&L: %s",
        total_trades, total_wins, total_losses, hit_rate,
        f"{sign}₹{total_pnl:,.2f}",
    )
    log.info("=" * 90)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_eod_report(
    portfolio: Portfolio,
    interval: str = "15m",
    save_dir: str | None = None,
) -> None:
    """
    Generate EOD charts + P&L statement for all instruments traded today.
    Called automatically at session end.
    """
    today_trades = _today_trades(portfolio)
    if not today_trades:
        log.info("No trades today — skipping EOD report.")
        return

    trades_by_sym = _trades_by_symbol(today_trades)
    _log_pnl_statement(trades_by_sym)

    chart_dir = Path(save_dir or f"output/paper_trading/{_TODAY}")
    log.info("Generating EOD charts → %s/", chart_dir)

    for symbol, trades in trades_by_sym.items():
        df = _fetch_today_candles(symbol, interval)
        if df is None:
            log.warning("No candle data for %s — skipping chart.", symbol)
            continue

        # Also pass any still-open positions for this symbol
        open_pos = [p for p in portfolio.positions if p.symbol == symbol]

        path = _plot_trade_chart(symbol, df, trades, open_pos, chart_dir)
        if path:
            log.info("  Chart saved: %s", path)

    log.info("EOD report complete. Charts saved to %s/", chart_dir)
