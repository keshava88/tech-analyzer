"""
Entry point: python -m tech_analyzer <SYMBOL> [options]

Examples:
    python -m tech_analyzer RELIANCE.NS
    python -m tech_analyzer TCS.NS --period 3mo --interval 1d
    python -m tech_analyzer INFY.NS --latest
    python -m tech_analyzer RELIANCE.NS --chart
    python -m tech_analyzer RELIANCE.NS --latest --chart --window 7
"""
import argparse
import sys

from tech_analyzer.data.historical import fetch
from tech_analyzer.patterns.detector import detect, detect_latest


def main():
    parser = argparse.ArgumentParser(
        prog="tech-analyzer",
        description="Candlestick pattern detector for Indian stocks (NSE/BSE)",
    )
    parser.add_argument("symbol", help="Ticker symbol e.g. RELIANCE.NS, TCS.BO")
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
        help="Specific patterns to detect (default: all)",
    )
    parser.add_argument(
        "--chart",
        action="store_true",
        help="Generate a candlestick chart PNG for each detected pattern",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=5,
        metavar="N",
        help="Candles before and after the pattern to include in chart (default: 5)",
    )
    parser.add_argument(
        "--chart-dir",
        default="output/charts",
        metavar="DIR",
        help="Directory to save chart PNGs (default: ./charts)",
    )
    args = parser.parse_args()

    print(f"\nFetching {args.symbol} | period={args.period} interval={args.interval} ...")
    try:
        df = fetch(args.symbol, period=args.period, interval=args.interval)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(df)} candles ({df.index[0].date()} → {df.index[-1].date()})\n")

    fn = detect_latest if args.latest else detect
    signals = fn(df, patterns=args.patterns)

    if signals.empty:
        print("No patterns detected.")
        return

    label = "latest candle" if args.latest else "full history"
    print(f"Patterns detected ({label}):\n")
    print(signals.to_string(index=False))
    print()

    if args.chart:
        from tech_analyzer.charts.plotter import plot_all_signals
        print(f"\nGenerating charts (window=±{args.window} candles) → {args.chart_dir}/")
        plot_all_signals(df, signals, window=args.window, save_dir=args.chart_dir)
        print(f"\nDone. {len(signals)} chart(s) saved to ./{args.chart_dir}/")


if __name__ == "__main__":
    main()
