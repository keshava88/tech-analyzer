"""
Entry point: python -m tech_analyzer <SYMBOL> [options]

Examples:
    python -m tech_analyzer RELIANCE.NS
    python -m tech_analyzer TCS.NS --period 3mo --interval 1d
    python -m tech_analyzer INFY.NS --latest
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


if __name__ == "__main__":
    main()
