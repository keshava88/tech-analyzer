"""Parallel multi-stock screener — scans a watchlist for latest-candle patterns."""
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from tech_analyzer.patterns.detector import detect_latest


def scan(
    symbols: list[str],
    period: str = "6mo",
    interval: str = "1d",
    trend_filter: bool = False,
    patterns: list[str] | None = None,
    max_workers: int = 8,
    verbose: bool = True,
    source: str = "yfinance",
) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """
    Scan a list of symbols for candlestick patterns on the latest candle.

    Args:
        symbols:      List of ticker symbols (e.g. ['RELIANCE.NS', 'TCS.NS'])
        period:       History to fetch via yfinance (e.g. '6mo')
        interval:     Candle interval (e.g. '1d', '15m')
        trend_filter: Only return signals aligned with the prevailing trend
        patterns:     Specific pattern keys to check (default: all)
        max_workers:  Thread pool size for parallel fetching
        verbose:      Print per-symbol progress lines
        source:       'yfinance' (default) or 'upstox'

    Returns:
        (results_df, errors)
        results_df — DataFrame with a leading 'symbol' column; empty if no hits
        errors     — list of (symbol, error_message) for failed fetches
    """
    if source == "upstox":
        from tech_analyzer.data.live import fetch
    else:
        from tech_analyzer.data.historical import fetch

    hits: list[pd.DataFrame] = []
    errors: list[tuple[str, str]] = []
    total = len(symbols)
    done = 0

    def _scan_one(symbol: str) -> tuple[str, pd.DataFrame]:
        if source == "upstox":
            df = fetch(symbol, interval=interval)
        else:
            df = fetch(symbol, period=period, interval=interval)
        sigs = detect_latest(df, patterns=patterns, trend_filter=trend_filter)
        return symbol, sigs

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_scan_one, sym): sym for sym in symbols}
        for future in as_completed(futures):
            sym = futures[future]
            done += 1
            try:
                symbol, sigs = future.result()
                n = len(sigs)
                if verbose:
                    marker = "+" if n > 0 else "."
                    print(f"  [{done:>2}/{total}] {marker} {symbol:<22} {n} signal(s)")
                if not sigs.empty:
                    sigs = sigs.copy()
                    sigs.insert(0, "symbol", symbol)
                    hits.append(sigs)
            except Exception as exc:
                if verbose:
                    print(f"  [{done:>2}/{total}] ! {sym:<22} ERROR: {exc}")
                errors.append((sym, str(exc)))

    if hits:
        out = pd.concat(hits, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
        return out, errors
    return pd.DataFrame(), errors
