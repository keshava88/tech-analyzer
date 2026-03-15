"""
Paper trading session — market-hours polling loop.

Polls Upstox for new candles and processes each close through the engine.
Runs from 9:15 to 15:30 IST. All positions are force-closed at 15:25.

Usage:
    session = PaperSession(symbols, interval="15m", capital=100000,
                           target_pct=2.0, stoploss_pct=1.0)
    session.run()
"""
import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd

from tech_analyzer.trading.portfolio import Portfolio, DEFAULT_PORTFOLIO_FILE
from tech_analyzer.trading.engine import process_candle

IST = ZoneInfo("Asia/Kolkata")

MARKET_OPEN  = dtime(9, 15)
MARKET_CLOSE = dtime(15, 30)
EOD_CUTOFF   = dtime(15, 25)   # close all positions at or after this time


def _ist_now() -> datetime:
    return datetime.now(tz=IST)


def _is_market_open(now: datetime | None = None) -> bool:
    t = (now or _ist_now()).time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


def _wait_for_candle_close(interval_minutes: int) -> None:
    """
    Sleep until the next candle boundary + 5 seconds buffer.
    e.g. for 15m: next boundary after 9:15 is 9:30, then 9:45, ...
    """
    now = _ist_now()
    minutes = now.minute
    seconds = now.second
    remainder = minutes % interval_minutes
    wait_m = (interval_minutes - remainder) if remainder > 0 else interval_minutes
    wait_s = wait_m * 60 - seconds + 5   # +5s buffer for data to arrive
    print(f"  Waiting {wait_s}s for next {interval_minutes}m candle close...", flush=True)
    time.sleep(wait_s)


def _interval_minutes(interval: str) -> int:
    mapping = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}
    return mapping.get(interval, 15)


class PaperSession:
    def __init__(
        self,
        symbols: list[str],
        interval: str = "15m",
        capital: float = 100_000.0,
        target_pct: float = 2.0,
        stoploss_pct: float = 1.0,
        fixed_units: int | None = None,
        patterns: list[str] | None = None,
        trend_filter: bool = True,
        portfolio_file=DEFAULT_PORTFOLIO_FILE,
        fresh: bool = False,
    ):
        self.symbols = symbols
        self.interval = interval
        self.target_pct = target_pct
        self.stoploss_pct = stoploss_pct
        self.fixed_units = fixed_units
        self.patterns = patterns
        self.trend_filter = trend_filter
        self.iv_minutes = _interval_minutes(interval)

        if fresh:
            self.portfolio = Portfolio(capital=capital, cash=capital)
        else:
            self.portfolio = Portfolio.load(portfolio_file)
            if self.portfolio.capital != capital and not self.portfolio.closed_trades and not self.portfolio.positions:
                # Fresh portfolio with custom capital
                self.portfolio.capital = capital
                self.portfolio.cash = capital

        self.portfolio_file = portfolio_file
        self._seen_candles: dict[str, str] = {}  # symbol → last processed candle datetime

    # ------------------------------------------------------------------ #
    # Core loop
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        print(f"\n=== Paper Trading Session ===")
        print(f"Symbols:   {', '.join(self.symbols)}")
        print(f"Interval:  {self.interval}  Target: +{self.target_pct}%  Stop: -{self.stoploss_pct}%")
        print(f"Capital:   INR {self.portfolio.cash:,.0f}")
        print(f"Started:   {_ist_now().strftime('%Y-%m-%d %H:%M:%S IST')}")
        print("=" * 44)

        try:
            while True:
                now = _ist_now()

                if not _is_market_open(now):
                    if now.time() < MARKET_OPEN:
                        wait = (
                            datetime.combine(now.date(), MARKET_OPEN, tzinfo=IST) - now
                        ).seconds
                        print(f"\nMarket not open yet. Waiting {wait//60}m {wait%60}s until 09:15 IST...")
                        time.sleep(min(wait, 60))
                    else:
                        print("\nMarket closed for the day.")
                        break
                    continue

                eod = now.time() >= EOD_CUTOFF
                self._process_all_symbols(eod=eod)
                self.portfolio.save(self.portfolio_file)
                self._print_status()

                if eod:
                    print("\nEOD: All positions closed. Session complete.")
                    break

                _wait_for_candle_close(self.iv_minutes)

        except KeyboardInterrupt:
            print("\n\nInterrupted. Saving portfolio state...")
            self.portfolio.save(self.portfolio_file)

        self._print_final_report()

    # ------------------------------------------------------------------ #
    # Per-candle processing
    # ------------------------------------------------------------------ #
    def _process_all_symbols(self, eod: bool = False) -> None:
        from tech_analyzer.data.live import fetch as upstox_fetch
        from tech_analyzer.patterns.detector import detect

        timestamp = _ist_now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] Processing {len(self.symbols)} symbol(s)  {'[EOD CLOSE]' if eod else ''}")

        for symbol in self.symbols:
            try:
                df = upstox_fetch(symbol, interval=self.interval)
            except Exception as e:
                print(f"  ! {symbol}: fetch error — {e}")
                continue

            # Get the most recent candle
            last_ts = str(df.index[-1])
            if self._seen_candles.get(symbol) == last_ts and not eod:
                print(f"  . {symbol}: no new candle yet")
                continue
            self._seen_candles[symbol] = last_ts

            # Detect patterns on the full history
            try:
                signals = detect(df, patterns=self.patterns, trend_filter=self.trend_filter)
                # Filter to latest candle only for entry decisions
                latest_signals = signals[signals["date"] == df.index[-1]].copy() if not signals.empty else signals
            except Exception as e:
                print(f"  ! {symbol}: detect error — {e}")
                latest_signals = pd.DataFrame()

            candle = {
                "date":  df.index[-1],
                "open":  df["open"].iloc[-1],
                "high":  df["high"].iloc[-1],
                "low":   df["low"].iloc[-1],
                "close": df["close"].iloc[-1],
            }

            events = process_candle(
                self.portfolio,
                symbol,
                candle,
                latest_signals,
                target_pct=self.target_pct,
                stoploss_pct=self.stoploss_pct,
                fixed_units=self.fixed_units,
                eod=eod,
            )

            for ev in events:
                self._print_event(ev)

            if not events:
                pos = self.portfolio.position_for(symbol)
                if pos:
                    print(f"  ~ {symbol:<22} HOLDING {pos.signal.upper()} @ {pos.entry_price}  "
                          f"tgt={pos.target_price}  stop={pos.stoploss_price}")
                else:
                    print(f"  . {symbol:<22} close={candle['close']:.2f}  no signal")

    @staticmethod
    def _print_event(ev: dict) -> None:
        sym = ev["symbol"]
        if ev["event"] == "open":
            print(
                f"  + {sym:<22} OPEN  {ev['signal'].upper():<8} "
                f"{ev['pattern']:<22} @ {ev['price']:.2f}  "
                f"x{ev['units']}  tgt={ev['target']}  stop={ev['stop']}"
            )
        else:
            sign = "+" if ev["pnl"] >= 0 else ""
            print(
                f"  {'W' if ev['pnl'] >= 0 else 'L'} {sym:<22} CLOSE {ev['signal'].upper():<8} "
                f"{ev['pattern']:<22} @ {ev['price']:.2f}  "
                f"reason={ev['reason']:<9} PnL={sign}{ev['pnl']:.2f} ({sign}{ev['pct']:.2f}%)"
            )

    def _print_status(self) -> None:
        s = self.portfolio.summary()
        open_count = len(self.portfolio.positions)
        print(
            f"\n  Portfolio | Cash: {s['cash']:>10,.0f}  "
            f"Open: {open_count}  "
            f"Trades: {s['trades']}  "
            f"Wins: {s['wins']}  "
            f"PnL: {s['total_pnl']:+,.0f}"
        )

    def _print_final_report(self) -> None:
        s = self.portfolio.summary()
        print(f"\n{'='*60}")
        print(f"  PAPER TRADING SESSION SUMMARY")
        print(f"{'='*60}")
        print(f"  Starting Capital : INR {s['capital']:>12,.0f}")
        print(f"  Current Cash     : INR {s['cash']:>12,.0f}")
        print(f"  Open Positions   : {len(self.portfolio.positions)}")
        print(f"  Total Trades     : {s['trades']}")
        print(f"  Wins / Losses    : {s['wins']} / {s['losses']}")
        print(f"  Hit Rate         : {s['hit_rate']}")
        print(f"  Total P&L        : INR {s['total_pnl']:>+12,.0f}")
        print(f"{'='*60}")

        if self.portfolio.closed_trades:
            print(f"\n  Trade Log:")
            print(f"  {'Symbol':<22} {'Pattern':<22} {'Dir':<8} {'Entry':>8} {'Exit':>8} {'PnL':>8} {'Reason'}")
            print(f"  {'-'*90}")
            for t in self.portfolio.closed_trades[-20:]:  # last 20 trades
                sign = "+" if t.pnl >= 0 else ""
                print(
                    f"  {t.symbol:<22} {t.pattern:<22} {t.signal:<8} "
                    f"{t.entry_price:>8.2f} {t.exit_price:>8.2f} "
                    f"{sign}{t.pnl:>8.2f} {t.exit_reason}"
                )
