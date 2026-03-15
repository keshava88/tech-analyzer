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
) -> pd.DataFrame:
    """
    Compute forward returns for each signal.

    Args:
        df:       Full OHLCV DataFrame (lowercase columns, DatetimeIndex)
        signals:  Output of detector.detect() — all historical signals
        forward:  Number of candles ahead to measure outcome

    Returns:
        DataFrame with one row per signal plus columns:
          entry_close, outcome_close, pct_change, win, candles_available
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
            win = None
        else:
            outcome = close_vals[i + forward]
            pct = (outcome - entry) / entry * 100
            if sig["signal"] == "bullish":
                win = pct > 0
            else:
                win = pct < 0

        rows.append({
            **sig.to_dict(),
            "entry_close":      round(entry, 2),
            "outcome_close":    round(outcome, 2) if not pd.isna(outcome) else None,
            "pct_change":       round(pct, 2) if not pd.isna(pct) else None,
            "win":              win,
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
        })

    out = pd.DataFrame(rows).sort_values(
        ["signal", "hit_rate"], ascending=[True, False]
    ).reset_index(drop=True)
    return out
