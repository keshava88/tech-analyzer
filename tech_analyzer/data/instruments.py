"""
Upstox instrument key lookup.

Lookup order:
  1. In-memory cache (per session)
  2. Upstox instrument master CSV (downloaded once per day, cached to disk)
  3. yfinance ISIN lookup (last-resort fallback)

The instrument master is a public file from Upstox — no auth required.
It is downloaded once per calendar day and cached at ~/.tech_analyzer/instruments_YYYY-MM-DD.csv.
"""
import csv
import gzip
import io
import logging
import urllib.request
from datetime import date
from pathlib import Path

import yfinance as yf

log = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".tech_analyzer"
_MASTER_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/complete.csv.gz"
)

_isin_cache: dict[str, str] = {}
_master_lookup: dict[str, str] | None = None  # "SYMBOL.NS" -> "NSE_EQ|ISIN"

_EXCHANGE_SUFFIX = {".NS": "NSE_EQ", ".BO": "BSE_EQ"}


# ---------------------------------------------------------------------------
# Instrument master download + parse
# ---------------------------------------------------------------------------

def _master_cache_path() -> Path:
    return _CACHE_DIR / f"instruments_{date.today()}.csv"


def _build_master_lookup() -> dict[str, str]:
    """
    Download (or load from disk cache) the Upstox complete instrument list
    and return a dict mapping 'SYMBOL.NS' / 'SYMBOL.BO' → instrument_key.
    """
    global _master_lookup
    if _master_lookup is not None:
        return _master_lookup

    cache = _master_cache_path()

    if cache.exists():
        csv_text = cache.read_text(encoding="utf-8")
    else:
        # Remove stale daily caches
        for old in _CACHE_DIR.glob("instruments_*.csv"):
            old.unlink(missing_ok=True)

        log.info("Downloading Upstox instrument master (one-time per day)...")
        req = urllib.request.Request(
            _MASTER_URL, headers={"User-Agent": "tech-analyzer/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            compressed = resp.read()
        csv_text = gzip.decompress(compressed).decode("utf-8")
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(csv_text, encoding="utf-8")

    lookup: dict[str, str] = {}
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        key = row.get("instrument_key", "").strip()
        symbol = row.get("tradingsymbol", "").strip()
        itype = row.get("instrument_type", "").strip()

        if not symbol or not key or itype != "EQUITY":
            continue

        # Derive exchange suffix from the instrument_key prefix
        if key.startswith("NSE_EQ|"):
            lookup[f"{symbol}.NS"] = key
        elif key.startswith("BSE_EQ|"):
            lookup[f"{symbol}.BO"] = key

    _master_lookup = lookup
    return lookup


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def symbol_to_instrument_key(symbol: str) -> str:
    """
    Convert a yfinance-style ticker to an Upstox instrument key.

    Examples:
        'RELIANCE.NS'  →  'NSE_EQ|INE002A01018'
        'TCS.NS'       →  'NSE_EQ|INE467B01029'

    Raises:
        ValueError: if the symbol cannot be resolved.
    """
    if symbol in _isin_cache:
        return _isin_cache[symbol]

    # Validate suffix
    suffix = next((s for s in _EXCHANGE_SUFFIX if symbol.upper().endswith(s)), None)
    if suffix is None:
        raise ValueError(
            f"Unrecognised exchange suffix in '{symbol}'. Use .NS for NSE or .BO for BSE."
        )

    # 1. Instrument master (most accurate — keys come directly from Upstox)
    try:
        master = _build_master_lookup()
        if symbol in master:
            _isin_cache[symbol] = master[symbol]
            return _isin_cache[symbol]
    except Exception as exc:
        log.warning("Instrument master unavailable (%s), falling back to yfinance ISIN lookup", exc)

    # 2. yfinance ISIN fallback
    segment = _EXCHANGE_SUFFIX[suffix]
    try:
        isin = yf.Ticker(symbol).isin
    except Exception as exc:
        raise ValueError(f"Could not fetch ISIN for '{symbol}': {exc}") from exc

    if not isin or isin == "-":
        raise ValueError(f"No ISIN found for '{symbol}' via yfinance.")

    key = f"{segment}|{isin}"
    _isin_cache[symbol] = key
    return key
