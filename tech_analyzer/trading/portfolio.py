"""
Paper trading portfolio — tracks cash, open positions, and closed trades.

State is persisted to JSON at ~/.tech_analyzer/paper_portfolio.json so that
a session can be resumed after restart.
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_PORTFOLIO_FILE = Path.home() / ".tech_analyzer" / "paper_portfolio.json"


@dataclass
class Position:
    symbol: str
    entry_date: str          # ISO datetime string
    entry_price: float
    units: int
    signal: str              # 'bullish' (long) or 'bearish' (short)
    pattern: str
    target_price: float
    stoploss_price: float


@dataclass
class ClosedTrade:
    symbol: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    units: int
    signal: str
    pattern: str
    exit_reason: str         # 'target', 'stoploss', 'signal', 'eod', 'manual'
    pnl: float               # INR profit/loss (positive = profit)
    pct: float               # % return on trade


@dataclass
class Portfolio:
    capital: float = 100_000.0
    cash: float = 100_000.0
    positions: list[Position] = field(default_factory=list)
    closed_trades: list[ClosedTrade] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def save(self, path: Path = DEFAULT_PORTFOLIO_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "capital":       self.capital,
            "cash":          self.cash,
            "positions":     [asdict(p) for p in self.positions],
            "closed_trades": [asdict(t) for t in self.closed_trades],
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path = DEFAULT_PORTFOLIO_FILE) -> "Portfolio":
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text())
        p = cls(
            capital=raw.get("capital", 100_000.0),
            cash=raw.get("cash", raw.get("capital", 100_000.0)),
        )
        p.positions = [Position(**pos) for pos in raw.get("positions", [])]
        p.closed_trades = [ClosedTrade(**t) for t in raw.get("closed_trades", [])]
        return p

    # ------------------------------------------------------------------ #
    # Operations
    # ------------------------------------------------------------------ #
    def open_position(self, pos: Position) -> bool:
        """
        Attempt to open a position. Returns False if insufficient cash.
        For a long trade: reserves entry_price * units.
        For a short trade: no cash reserved (simulated short).
        """
        if pos.signal == "bullish":
            cost = pos.entry_price * pos.units
            if cost > self.cash:
                return False
            self.cash -= cost
        self.positions.append(pos)
        return True

    def close_position(
        self,
        pos: Position,
        exit_price: float,
        exit_reason: str,
        exit_date: Optional[str] = None,
    ) -> ClosedTrade:
        """Close a position and record the trade."""
        if pos.signal == "bullish":
            pnl = (exit_price - pos.entry_price) * pos.units
            pct = (exit_price - pos.entry_price) / pos.entry_price * 100
            self.cash += pos.entry_price * pos.units + pnl
        else:  # bearish (short)
            pnl = (pos.entry_price - exit_price) * pos.units
            pct = (pos.entry_price - exit_price) / pos.entry_price * 100

        trade = ClosedTrade(
            symbol=pos.symbol,
            entry_date=pos.entry_date,
            exit_date=exit_date or datetime.now().isoformat(),
            entry_price=pos.entry_price,
            exit_price=exit_price,
            units=pos.units,
            signal=pos.signal,
            pattern=pos.pattern,
            exit_reason=exit_reason,
            pnl=round(pnl, 2),
            pct=round(pct, 2),
        )
        self.positions.remove(pos)
        self.closed_trades.append(trade)
        return trade

    def position_for(self, symbol: str) -> Optional[Position]:
        """Return the open position for a symbol, or None."""
        for p in self.positions:
            if p.symbol == symbol:
                return p
        return None

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #
    def summary(self) -> dict:
        """Return a quick stats dict for display."""
        open_value = sum(
            p.entry_price * p.units for p in self.positions if p.signal == "bullish"
        )
        total_pnl = sum(t.pnl for t in self.closed_trades)
        wins = [t for t in self.closed_trades if t.pnl > 0]
        losses = [t for t in self.closed_trades if t.pnl <= 0]
        n = len(self.closed_trades)
        return {
            "capital":      self.capital,
            "cash":         round(self.cash, 2),
            "open_value":   round(open_value, 2),
            "total_value":  round(self.cash + open_value, 2),
            "total_pnl":    round(total_pnl, 2),
            "trades":       n,
            "wins":         len(wins),
            "losses":       len(losses),
            "hit_rate":     f"{len(wins)/n*100:.1f}%" if n > 0 else "-",
            "avg_pnl":      round(total_pnl / n, 2) if n > 0 else 0,
        }
