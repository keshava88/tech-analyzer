"""
Entry point: python -m tech_analyzer <SYMBOL> [options]

Single-stock analysis:
    python -m tech_analyzer RELIANCE.NS
    python -m tech_analyzer TCS.NS --period 3mo --interval 1d
    python -m tech_analyzer INFY.NS --latest
    python -m tech_analyzer RELIANCE.NS --chart
    python -m tech_analyzer RELIANCE.NS --latest --chart --window 7

Multi-stock screener:
    python -m tech_analyzer --watchlist nifty50
    python -m tech_analyzer --watchlist nifty_bank --trend-filter
    python -m tech_analyzer --watchlist my_stocks.txt --period 3mo
"""
import argparse
import sys
from datetime import datetime
import uuid

from tech_analyzer.data.historical import fetch
from tech_analyzer.patterns.detector import detect, detect_latest


def main():
    parser = argparse.ArgumentParser(
        prog="tech-analyzer",
        description="Candlestick pattern detector for Indian stocks (NSE/BSE)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "symbol",
        nargs="?",
        help="Ticker symbol e.g. RELIANCE.NS, TCS.BO (omit when using --watchlist)",
    )
    parser.add_argument(
        "--watchlist",
        metavar="NAME_OR_FILE",
        help=(
            "Scan a watchlist instead of a single symbol.\n"
            "Built-in names: 'nifty50', 'nifty_bank'\n"
            "Or pass a path to a .txt file (one ticker per line, # for comments)"
        ),
    )
    parser.add_argument("--period", default="6mo", help="History period (default: 6mo)")
    parser.add_argument("--interval", default="1d", help="Candle interval (default: 1d)")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Show only patterns on the most recent candle",
    )
    parser.add_argument(
        "--patterns",
        nargs="+",
        default=None,
        metavar="PATTERN",
        help=(
            "Specific patterns to detect (default: all). "
            "Use TA-Lib key names. Available patterns:\n\n"
            "  SINGLE CANDLE\n"
            "    CDLDOJI           - Doji: open ~= close, market indecision\n"
            "    CDLDRAGONFLYDOJI  - Dragonfly Doji: long lower wick, bullish reversal\n"
            "    CDLGRAVESTONEDOJI - Gravestone Doji: long upper wick, bearish reversal\n"
            "    CDLHAMMER         - Hammer: small body, long lower wick, bullish reversal\n"
            "    CDLHANGINGMAN     - Hanging Man: hammer shape at top of uptrend, bearish warning\n"
            "    CDLINVERTEDHAMMER - Inverted Hammer: long upper wick, potential bullish reversal\n"
            "    CDLSHOOTINGSTAR   - Shooting Star: long upper wick at top of uptrend, bearish\n"
            "    CDLMARUBOZU       - Marubozu: no wicks, strong directional momentum\n"
            "    CDLSPINNINGTOP    - Spinning Top: small body, both wicks present, indecision\n\n"
            "  TWO CANDLE\n"
            "    CDLENGULFING      - Engulfing: second candle fully engulfs the first, reversal\n"
            "    CDLHARAMI         - Harami: small candle inside prior candle, reversal warning\n"
            "    CDLHARAMICROSS    - Harami Cross: doji inside prior candle, stronger reversal signal\n"
            "    CDLPIERCING       - Piercing Line: bullish reversal after downtrend\n"
            "    CDLDARKCLOUDCOVER - Dark Cloud Cover: bearish reversal after uptrend\n\n"
            "  THREE CANDLE\n"
            "    CDLMORNINGSTAR      - Morning Star: bullish reversal at bottom, 3-candle pattern\n"
            "    CDLEVENINGSTAR      - Evening Star: bearish reversal at top, 3-candle pattern\n"
            "    CDLMORNINGDOJISTAR  - Morning Doji Star: stronger morning star with doji middle\n"
            "    CDLEVENINGDOJISTAR  - Evening Doji Star: stronger evening star with doji middle\n"
            "    CDL3WHITESOLDIERS   - Three White Soldiers: 3 consecutive bullish candles, strong uptrend\n"
            "    CDL3BLACKCROWS      - Three Black Crows: 3 consecutive bearish candles, strong downtrend\n"
            "    CDL3INSIDE          - Three Inside Up/Down: confirmed harami reversal\n"
            "    CDL3OUTSIDE         - Three Outside Up/Down: confirmed engulfing reversal\n\n"
            "  Example: --patterns CDLHAMMER CDLENGULFING CDLMORNINGSTAR"
        ),
    )
    parser.add_argument(
        "--trend-filter",
        action="store_true",
        help="Only show patterns aligned with the prevailing EMA20/EMA50 trend",
    )
    parser.add_argument(
        "--chart",
        action="store_true",
        help="Generate a candlestick chart PNG for each detected pattern",
    )
    parser.add_argument(
        "--sr",
        action="store_true",
        help="Annotate charts with support/resistance levels (requires --chart)",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=10,
        metavar="N",
        help="Candles before and after the pattern to include in chart (default: 10)",
    )
    parser.add_argument(
        "--chart-dir",
        default=None,
        metavar="DIR",
        help="Directory to save chart PNGs (default: output/charts/YYYY-MM-DD)",
    )
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Run backtest: measure hit rate and returns for all detected patterns",
    )
    parser.add_argument(
        "--forward",
        type=int,
        default=10,
        metavar="N",
        help="Candles ahead to measure backtest outcome (default: 10)",
    )
    parser.add_argument(
        "--units",
        type=int,
        default=10,
        metavar="N",
        help="Shares traded per signal for INR P&L calculation (default: 10)",
    )
    parser.add_argument(
        "--backtest-patterns",
        nargs="+",
        default=None,
        metavar="PATTERN",
        help=(
            "Limit backtest to specific patterns (default: same as --patterns / all).\n"
            "Uses the same TA-Lib key names as --patterns.\n"
            "Example: --backtest-patterns CDLHAMMER CDLENGULFING CDLMORNINGSTAR"
        ),
    )
    parser.add_argument(
        "--save-backtest",
        default=None,
        metavar="FILE",
        help="Save backtest summary to a CSV file",
    )
    args = parser.parse_args()

    if args.watchlist and args.symbol:
        parser.error("--watchlist and a positional symbol are mutually exclusive.")

    if not args.watchlist and not args.symbol:
        parser.error("Provide a ticker symbol or use --watchlist.")

    if args.watchlist:
        _run_screen(args)
    else:
        _run_single(args)


def _run_screen(args) -> None:
    from tech_analyzer.screener.watchlists import load
    from tech_analyzer.screener.scanner import scan

    try:
        symbols = load(args.watchlist)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading watchlist: {e}", file=sys.stderr)
        sys.exit(1)

    tf_label = "on" if args.trend_filter else "off"
    print(
        f"\nScreening {len(symbols)} stocks | "
        f"period={args.period} interval={args.interval} | "
        f"trend-filter={tf_label}"
    )
    print("-" * 62)

    results, errors = scan(
        symbols,
        period=args.period,
        interval=args.interval,
        trend_filter=args.trend_filter,
        patterns=args.patterns,
    )

    print()
    if results.empty:
        print("No patterns found on latest candle across the watchlist.")
    else:
        hit_count = results["symbol"].nunique()
        print("=" * 62)
        print(f"RESULTS: {hit_count}/{len(symbols)} stocks with signals on latest candle\n")
        print(results.to_string(index=False))

    if errors:
        print(f"\n{len(errors)} symbol(s) failed to fetch:")
        for sym, err in errors:
            print(f"  {sym}: {err}")


def _run_single(args) -> None:
    if args.chart_dir is None:
        uid = uuid.uuid4().hex[:6]
        args.chart_dir = f"output/charts/{args.symbol}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')}_{uid}"

    print(f"\nFetching {args.symbol} | period={args.period} interval={args.interval} ...")
    try:
        df = fetch(args.symbol, period=args.period, interval=args.interval)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(df)} candles ({df.index[0].date()} to {df.index[-1].date()})\n")

    fn = detect_latest if args.latest else detect
    signals = fn(df, patterns=args.patterns, trend_filter=args.trend_filter)

    if signals.empty:
        print("No patterns detected.")
        return

    label = "latest candle" if args.latest else "full history"
    print(f"Patterns detected ({label}):\n")
    print(signals.to_string(index=False))
    print()

    if args.chart:
        from tech_analyzer.charts.plotter import plot_all_signals
        sr_label = " + S/R" if args.sr else ""
        print(f"\nGenerating charts (window=+-{args.window} candles{sr_label}) -> {args.chart_dir}/")
        plot_all_signals(df, signals, window=args.window, save_dir=args.chart_dir, show_sr=args.sr)
        print(f"\nDone. {len(signals)} chart(s) saved to ./{args.chart_dir}/")

    if args.backtest:
        _run_backtest(df, signals, args)


def _run_backtest(df, signals, args) -> None:
    from tech_analyzer.analysis.backtest import run, summarize, totals

    if signals.empty:
        print("No signals to backtest.")
        return

    bt_signals = signals
    if args.backtest_patterns:
        from tech_analyzer.patterns.detector import PATTERNS
        # Resolve TA-Lib keys → human-readable names used in the signals DataFrame
        names = []
        for key in args.backtest_patterns:
            key = key.upper()
            if key not in PATTERNS:
                print(f"Warning: unknown pattern '{key}', skipping.", file=sys.stderr)
                continue
            names.append(PATTERNS[key])
        bt_signals = signals[signals["pattern"].isin(names)].reset_index(drop=True)
        if bt_signals.empty:
            print("No signals match the specified --backtest-patterns.")
            return

    label = f"forward={args.forward} candles | units={args.units}"
    if args.backtest_patterns:
        label += f" | patterns={len(bt_signals['pattern'].unique())}"
    print(f"\nBacktesting {len(bt_signals)} signal(s) | {label} ...\n")

    results = run(df, bt_signals, forward=args.forward, units=args.units)
    summary = summarize(results)

    if summary.empty:
        print("Not enough data to compute hit rates (signals too close to end of history).")
        return

    print(summary.to_string(index=False))

    excluded = results["win"].isna().sum()
    if excluded:
        print(f"\n  ({excluded} signal(s) excluded - fewer than {args.forward} candles remaining)")

    t = totals(results)
    if t:
        print(f"\n{'='*62}")
        print(f"  OVERALL  |  Signals: {t['total_signals']}  Eligible: {t['eligible']}  Units: {args.units}")
        print(f"  Wins: {t['wins']}  Losses: {t['losses']}  Hit Rate: {t['hit_rate']}")
        print(f"  Gain:  {t['total_gain']:>8}  /  INR {t['gain_inr']:>10}")
        print(f"  Loss:  {t['total_loss']:>8}  /  INR {t['loss_inr']:>10}")
        print(f"  Net:   {t['net_return']:>8}  /  INR {t['net_inr']:>10}  (avg {t['avg_return']}/signal)")
        print(f"{'='*62}")

    if args.save_backtest:
        summary.to_csv(args.save_backtest, index=False)
        print(f"\nSummary saved to {args.save_backtest}")


if __name__ == "__main__":
    main()
