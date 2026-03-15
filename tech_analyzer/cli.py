"""
Entry point: python -m tech_analyzer <SYMBOL> [options]

Single-stock analysis (yfinance, default):
    python -m tech_analyzer RELIANCE.NS
    python -m tech_analyzer TCS.NS --period 3mo --interval 1d
    python -m tech_analyzer RELIANCE.NS --chart --sr

Single-stock intraday analysis (Upstox):
    python -m tech_analyzer --auth                                # one-time login
    python -m tech_analyzer RELIANCE.NS --source upstox --interval 15m
    python -m tech_analyzer RELIANCE.NS --source upstox --interval 1h --latest

Multi-stock screener:
    python -m tech_analyzer --watchlist nifty50
    python -m tech_analyzer --watchlist nifty_bank --trend-filter
    python -m tech_analyzer --watchlist nifty50 --source upstox --interval 15m
"""
import argparse
import sys
from datetime import datetime
import uuid

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
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Run Upstox OAuth2 login flow and save access token (one-time setup)",
    )
    parser.add_argument(
        "--source",
        choices=["yfinance", "upstox"],
        default="yfinance",
        help="Data source: 'yfinance' (default) or 'upstox' (requires --auth first)",
    )
    parser.add_argument("--period", default="6mo", help="History period for yfinance (default: 6mo)")
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
    args = parser.parse_args()

    if args.auth:
        _run_auth()
        return

    if args.watchlist and args.symbol:
        parser.error("--watchlist and a positional symbol are mutually exclusive.")

    if not args.watchlist and not args.symbol:
        parser.error("Provide a ticker symbol, --watchlist, or --auth.")

    if args.watchlist:
        _run_screen(args)
    else:
        _run_single(args)


def _fetch(args, symbol: str):
    """Call the right data source based on --source flag."""
    if args.source == "upstox":
        from tech_analyzer.data.live import fetch as upstox_fetch
        return upstox_fetch(symbol, interval=args.interval)
    from tech_analyzer.data.historical import fetch as yf_fetch
    return yf_fetch(symbol, period=args.period, interval=args.interval)


def _run_auth() -> None:
    import os
    from dotenv import load_dotenv
    from tech_analyzer.data.auth import run_oauth_flow

    load_dotenv()
    api_key     = os.getenv("UPSTOX_API_KEY")
    api_secret  = os.getenv("UPSTOX_API_SECRET")
    redirect_uri = os.getenv("UPSTOX_REDIRECT_URI", "http://127.0.0.1:8000/callback")

    if not api_key or not api_secret:
        print(
            "Error: UPSTOX_API_KEY and UPSTOX_API_SECRET must be set in your .env file.\n"
            "Copy .env.example to .env and fill in your credentials.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        run_oauth_flow(api_key, api_secret, redirect_uri)
        print("\nSetup complete. You can now use --source upstox.")
    except Exception as e:
        print(f"Auth failed: {e}", file=sys.stderr)
        sys.exit(1)


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
        source=args.source,
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

    src_label = f"source={args.source} interval={args.interval}"
    if args.source == "yfinance":
        src_label = f"period={args.period} interval={args.interval}"
    print(f"\nFetching {args.symbol} | {src_label} ...")
    try:
        df = _fetch(args, args.symbol)
    except (ValueError, RuntimeError) as e:
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


if __name__ == "__main__":
    main()
