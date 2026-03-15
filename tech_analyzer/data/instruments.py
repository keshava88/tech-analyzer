"""
Upstox instrument key lookup using yfinance ISIN data.

Maps yfinance-style tickers (e.g. 'RELIANCE.NS') to Upstox instrument keys
(e.g. 'NSE_EQ|INE002A01018') by looking up the ISIN via yfinance.

ISINs are cached in memory per session — no file download required.
"""
import yfinance as yf

_EXCHANGE_SEGMENT = {
    ".NS": "NSE_EQ",
    ".BO": "BSE_EQ",
}

_isin_cache: dict[str, str] = {}


def symbol_to_instrument_key(symbol: str) -> str:
    """
    Convert a yfinance-style ticker to an Upstox instrument key.

    Examples:
        'RELIANCE.NS'  →  'NSE_EQ|INE002A01018'
        'TCS.NS'       →  'NSE_EQ|INE467B01029'

    Raises:
        ValueError: if the symbol suffix is not recognised or ISIN cannot be found.
    """
    if symbol in _isin_cache:
        return _isin_cache[symbol]

    suffix = None
    for sfx in _EXCHANGE_SEGMENT:
        if symbol.upper().endswith(sfx):
            suffix = sfx
            break

    if suffix is None:
        raise ValueError(
            f"Unrecognised exchange suffix in '{symbol}'. Use .NS for NSE or .BO for BSE."
        )

    segment = _EXCHANGE_SEGMENT[suffix]

    try:
        isin = yf.Ticker(symbol).isin
    except Exception as e:
        raise ValueError(f"Could not fetch ISIN for '{symbol}': {e}") from e

    if not isin or isin == "-":
        raise ValueError(f"No ISIN found for '{symbol}' via yfinance.")

    key = f"{segment}|{isin}"
    _isin_cache[symbol] = key
    return key
