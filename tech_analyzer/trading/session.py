"""
Paper trading session — market-hours polling loop.

Polls Upstox for new candles and processes each close through the engine.
Runs from 9:15 to 15:30 IST. All positions are force-closed at 15:25.

Usage:
    session = PaperSession(symbols, interval="15m", capital=100000,
                           target_pct=2.0, stoploss_pct=1.0)
    session.run()
"""
import logging
import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd

from tech_analyzer.trading.portfolio import Portfolio, DEFAULT_PORTFOLIO_FILE
from tech_analyzer.trading.engine import process_candle

log = logging.getLogger(__name__)

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
    log.info("Waiting %ds for next %dm candle close...", wait_s, interval_minutes)
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
                self.portfolio.capital = capital
                self.portfolio.cash = capital

        self.portfolio_file = portfolio_file
        self._seen_candles: dict[str, str] = {}   # symbol → last processed candle datetime
        self._last_price: dict[str, float] = {}   # symbol → last known close price

    # ------------------------------------------------------------------ #
    # Core loop
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        log.info("=" * 44)
        log.info("Paper Trading Session")
        log.info("Symbols  : %s", ", ".join(self.symbols))
        log.info("Interval : %s  Target: +%s%%  Stop: -%s%%", self.interval, self.target_pct, self.stoploss_pct)
        log.info("Capital  : INR %s", f"{self.portfolio.cash:,.0f}")
        log.info("=" * 44)

        try:
            while True:
                now = _ist_now()

                if not _is_market_open(now):
                    if now.time() < MARKET_OPEN:
                        wait = (
                            datetime.combine(now.date(), MARKET_OPEN, tzinfo=IST) - now
                        ).seconds
                        log.info("Market not open yet. Waiting %dm %ds until 09:15 IST...", wait // 60, wait % 60)
                        time.sleep(min(wait, 60))
                    else:
                        log.info("Market closed for the day.")
                        break
                    continue

                eod = now.time() >= EOD_CUTOFF
                self._process_all_symbols(eod=eod)
                self.portfolio.save(self.portfolio_file)
                self._log_symbol_table()
                self._log_status()

                if eod:
                    log.info("EOD: All positions closed. Session complete.")
                    break

                _wait_for_candle_close(self.iv_minutes)

        except KeyboardInterrupt:
            log.info("Interrupted. Saving portfolio state...")
            self.portfolio.save(self.portfolio_file)

        self._log_final_report()

    # ------------------------------------------------------------------ #
    # Per-candle processing
    # ------------------------------------------------------------------ #
    def _process_all_symbols(self, eod: bool = False) -> None:
        from tech_analyzer.data.live import fetch as upstox_fetch
        from tech_analyzer.patterns.detector import detect

        log.info("Processing %d symbol(s)%s", len(self.symbols), "  [EOD CLOSE]" if eod else "")

        for symbol in self.symbols:
            try:
                df = upstox_fetch(symbol, interval=self.interval)
            except Exception as e:
                log.error("! %s: fetch error — %s", symbol, e)
                continue

            last_ts = str(df.index[-1])
            last_close = float(df["close"].iloc[-1])
            self._last_price[symbol] = last_close
            log.debug(
                "%s: latest candle=%s  close=%.2f  candles_fetched=%d",
                symbol, last_ts, last_close, len(df),
            )
            if self._seen_candles.get(symbol) == last_ts and not eod:
                log.info(". %-22s no new candle  (last=%s)", symbol, last_ts)
                continue
            self._seen_candles[symbol] = last_ts
            log.debug("%s: new candle accepted", symbol)

            try:
                signals = detect(df, patterns=self.patterns, trend_filter=self.trend_filter)
                latest_signals = signals[signals["date"] == df.index[-1]].copy() if not signals.empty else signals
            except Exception as e:
                log.error("! %s: detect error — %s", symbol, e)
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
                self._log_event(ev)

            if not events:
                pos = self.portfolio.position_for(symbol)
                if pos:
                    log.info(
                        "~ %-22s HOLDING %-8s @ %-10s tgt=%-10s stop=%s",
                        symbol, pos.signal.upper(), pos.entry_price,
                        pos.target_price, pos.stoploss_price,
                    )
                else:
                    log.info(". %-22s close=%.2f  no signal", symbol, candle["close"])

    @staticmethod
    def _log_event(ev: dict) -> None:
        sym = ev["symbol"]
        if ev["event"] == "open":
            log.info(
                "+ %-22s OPEN  %-8s %-22s @ %-10.2f x%d  tgt=%s  stop=%s",
                sym, ev["signal"].upper(), ev["pattern"],
                ev["price"], ev["units"], ev["target"], ev["stop"],
            )
        else:
            sign = "+" if ev["pnl"] >= 0 else ""
            level = "W" if ev["pnl"] >= 0 else "L"
            log.info(
                "%s %-22s CLOSE %-8s %-22s @ %-10.2f reason=%-9s PnL=%s%s (%s%s%%)",
                level, sym, ev["signal"].upper(), ev["pattern"],
                ev["price"], ev["reason"],
                sign, ev["pnl"], sign, ev["pct"],
            )

    def _log_symbol_table(self) -> None:
        from tech_analyzer.data.live import fetch_ltp

        # Fetch real-time LTP for all symbols; fall back to last candle close on failure
        try:
            ltp_map = fetch_ltp(self.symbols)
        except Exception:
            ltp_map = {}

        log.info("%-24s %10s  %-12s %10s %10s %10s", "Symbol", "LTP", "State", "Entry", "Target", "Stop")
        log.info("-" * 82)
        for symbol in self.symbols:
            price = ltp_map.get(symbol) or self._last_price.get(symbol)
            price_str = f"{price:.2f}" if price is not None else "N/A"
            pos = self.portfolio.position_for(symbol)
            if pos:
                state = f"HOLD {pos.signal.upper()}"
                log.info(
                    "%-24s %10s  %-12s %10.2f %10.2f %10.2f",
                    symbol, price_str, state,
                    pos.entry_price, pos.target_price, pos.stoploss_price,
                )
            else:
                log.info("%-24s %10s  %-12s", symbol, price_str, "watching")
        log.info("-" * 82)

    def _log_status(self) -> None:
        s = self.portfolio.summary()
        log.info(
            "Portfolio | Cash: %10s  Open: %d  Trades: %d  Wins: %d  PnL: %s",
            f"{s['cash']:,.0f}", len(self.portfolio.positions),
            s["trades"], s["wins"], f"{s['total_pnl']:+,.0f}",
        )

    def _log_final_report(self) -> None:
        s = self.portfolio.summary()
        log.info("=" * 60)
        log.info("PAPER TRADING SESSION SUMMARY")
        log.info("=" * 60)
        log.info("Starting Capital : INR %14s", f"{s['capital']:,.0f}")
        log.info("Current Cash     : INR %14s", f"{s['cash']:,.0f}")
        log.info("Open Positions   : %d", len(self.portfolio.positions))
        log.info("Total Trades     : %d", s["trades"])
        log.info("Wins / Losses    : %d / %d", s["wins"], s["losses"])
        log.info("Hit Rate         : %s", s["hit_rate"])
        log.info("Total P&L        : INR %s", f"{s['total_pnl']:+,.0f}")
        log.info("=" * 60)

        if self.portfolio.closed_trades:
            log.info("Trade Log:")
            log.info("  %-22s %-22s %-8s %8s %8s %8s %s", "Symbol", "Pattern", "Dir", "Entry", "Exit", "PnL", "Reason")
            log.info("  %s", "-" * 90)
            for t in self.portfolio.closed_trades[-20:]:
                sign = "+" if t.pnl >= 0 else ""
                log.info(
                    "  %-22s %-22s %-8s %8.2f %8.2f %s%8.2f %s",
                    t.symbol, t.pattern, t.signal,
                    t.entry_price, t.exit_price, sign, t.pnl, t.exit_reason,
                )
