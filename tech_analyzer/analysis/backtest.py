"""
Pattern backtesting — measures how each historical signal performed
over the next N candles.

Win definition:
  Bullish signal: close[signal + forward] > entry_close  → win
  Bearish signal: close[signal + forward] < entry_close  → win

Signals too close to the end of the data (< forward candles remaining)
are excluded from the summary stats but still reported with NaN outcome.
"""
import pandas as pd


def run(
    df: pd.DataFrame,
    signals: pd.DataFrame,
    forward: int = 10,
    units: int = 10,
) -> pd.DataFrame:
    """
    Compute forward returns for each signal.

    Args:
        df:       Full OHLCV DataFrame (lowercase columns, DatetimeIndex)
        signals:  Output of detector.detect() — all historical signals
        forward:  Number of candles ahead to measure outcome
        units:    Number of shares traded per signal (for INR P&L)

    Returns:
        DataFrame with one row per signal plus columns:
          entry_close, outcome_close, pct_change, inr_pnl, win, candles_available
    """
    if signals.empty:
        return pd.DataFrame()

    closes = df["close"].astype(float)
    close_vals = closes.values
    close_idx = {ts: i for i, ts in enumerate(df.index)}

    rows = []
    for _, sig in signals.iterrows():
        sig_date = sig["date"]
        i = close_idx.get(sig_date)
        if i is None:
            continue

        entry = close_vals[i]
        remaining = len(close_vals) - i - 1
        avail = min(forward, remaining)

        if avail < forward:
            outcome = float("nan")
            pct = float("nan")
            inr_pnl = float("nan")
            win = None
        else:
            outcome = close_vals[i + forward]
            pct = (outcome - entry) / entry * 100
            inr_pnl = (outcome - entry) * units
            if sig["signal"] == "bullish":
                win = pct > 0
            else:
                win = pct < 0

        rows.append({
            **sig.to_dict(),
            "entry_close":       round(entry, 2),
            "outcome_close":     round(outcome, 2) if not pd.isna(outcome) else None,
            "pct_change":        round(pct, 2) if not pd.isna(pct) else None,
            "inr_pnl":           round(inr_pnl, 2) if not pd.isna(inr_pnl) else None,
            "win":               win,
            "candles_available": avail,
        })

    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate per-signal results into a per-pattern summary table.

    Returns DataFrame with columns:
      pattern, signal, total, eligible, wins, hit_rate,
      avg_return, avg_win, avg_loss, best, worst
    """
    if results.empty:
        return pd.DataFrame()

    # Only include rows with a full forward window
    eligible = results[results["win"].notna()].copy()
    eligible["win"] = eligible["win"].astype(bool)

    rows = []
    for (pattern, signal), grp in eligible.groupby(["pattern", "signal"]):
        total_all = len(results[
            (results["pattern"] == pattern) & (results["signal"] == signal)
        ])
        n = len(grp)
        wins = grp["win"].sum()
        pcts = grp["pct_change"].astype(float)

        inr = grp["inr_pnl"].astype(float)
        rows.append({
            "pattern":    pattern,
            "signal":     signal,
            "total":      total_all,
            "eligible":   n,
            "wins":       int(wins),
            "hit_rate":   f"{wins / n * 100:.1f}%" if n > 0 else "-",
            "avg_return": f"{pcts.mean():+.2f}%",
            "avg_win":    f"{pcts[grp['win']].mean():+.2f}%" if wins > 0 else "-",
            "avg_loss":   f"{pcts[~grp['win']].mean():+.2f}%" if (~grp["win"]).any() else "-",
            "best":       f"{pcts.max():+.2f}%",
            "worst":      f"{pcts.min():+.2f}%",
            "net_inr":    f"{inr.sum():+.0f}",
        })

    out = pd.DataFrame(rows).sort_values(
        ["signal", "hit_rate"], ascending=[True, False]
    ).reset_index(drop=True)
    return out


def totals(results: pd.DataFrame) -> dict:
    """
    Compute overall summary stats across all eligible signals.

    Returns a dict with:
      total_signals, eligible, wins, losses, hit_rate,
      total_gain (sum of winning pct_changes),
      total_loss (sum of losing pct_changes),
      net_return  (sum of all pct_changes),
      avg_return
    """
    eligible = results[results["win"].notna()].copy()
    eligible["win"] = eligible["win"].astype(bool)

    if eligible.empty:
        return {}

    pcts = eligible["pct_change"].astype(float)
    inr  = eligible["inr_pnl"].astype(float)
    wins = eligible["win"]

    return {
        "total_signals": len(results),
        "eligible":      len(eligible),
        "wins":          int(wins.sum()),
        "losses":        int((~wins).sum()),
        "hit_rate":      f"{wins.mean() * 100:.1f}%",
        "total_gain":    f"{pcts[wins].sum():+.2f}%",
        "total_loss":    f"{pcts[~wins].sum():+.2f}%",
        "net_return":    f"{pcts.sum():+.2f}%",
        "avg_return":    f"{pcts.mean():+.2f}%",
        "gain_inr":      f"+{inr[wins].sum():,.0f}",
        "loss_inr":      f"{inr[~wins].sum():,.0f}",
        "net_inr":       f"{inr.sum():+,.0f}",
    }
