"""
Intraday OHLCV data from Upstox REST API (HistoryV3Api).

Returns the same DataFrame format as historical.fetch() so the rest of the
pipeline (detector, plotter, screener) works without modification.

Supported intervals:
    1m, 5m, 15m, 30m, 1h, 1d, 1wk

Requires a valid Upstox access token obtained via:
    python -m tech_analyzer --auth
"""
from datetime import date, timedelta

import pandas as pd
import upstox_client

# Maps user-facing interval strings → (unit, interval) for Upstox HistoryV3Api
# unit: 'minutes' | 'hours' | 'days' | 'weeks' | 'months'
# interval: integer candle size
INTERVAL_MAP: dict[str, tuple[str, int]] = {
    "1m":  ("minutes", 1),
    "5m":  ("minutes", 5),
    "15m": ("minutes", 15),
    "30m": ("minutes", 30),
    "1h":  ("hours",   1),
    "1d":  ("days",    1),
    "1wk": ("weeks",   1),
}

# Default lookback (days) per interval — Upstox limits intraday ranges
_DEFAULT_LOOKBACK: dict[str, int] = {
    "1m":  2,
    "5m":  5,
    "15m": 7,
    "30m": 10,
    "1h":  30,
    "1d":  180,
    "1wk": 365,
}


def fetch(
    symbol: str,
    interval: str = "15m",
    from_date: str | None = None,
    to_date: str | None = None,
    access_token: str | None = None,
) -> pd.DataFrame:
    """
    Fetch intraday/daily OHLCV from Upstox for a given symbol.

    Args:
        symbol:       NSE/BSE ticker, e.g. 'RELIANCE.NS', 'TCS.NS'
        interval:     Candle interval: '1m', '5m', '15m', '30m', '1h', '1d', '1wk'
        from_date:    Start date 'YYYY-MM-DD' (default: interval-appropriate lookback)
        to_date:      End date   'YYYY-MM-DD' (default: today)
        access_token: Upstox access token (default: load from ~/.tech_analyzer/)

    Returns:
        DataFrame indexed by datetime with lowercase columns: open, high, low, close, volume

    Raises:
        RuntimeError: if no access token is available
        ValueError:   if symbol not found or no data returned
    """
    from tech_analyzer.data.auth import load_token
    from tech_analyzer.data.instruments import symbol_to_instrument_key

    if access_token is None:
        access_token = load_token()
        if access_token is None:
            raise RuntimeError(
                "No Upstox access token found. "
                "Run:  python -m tech_analyzer --auth"
            )

    if interval not in INTERVAL_MAP:
        raise ValueError(
            f"Unknown interval '{interval}'. "
            f"Supported: {', '.join(INTERVAL_MAP.keys())}"
        )
    unit, iv = INTERVAL_MAP[interval]

    instrument_key = symbol_to_instrument_key(symbol)

    today = date.today()
    if to_date is None:
        to_date = today.strftime("%Y-%m-%d")
    if from_date is None:
        lookback = _DEFAULT_LOOKBACK.get(interval, 30)
        from_date = (today - timedelta(days=lookback)).strftime("%Y-%m-%d")

    configuration = upstox_client.Configuration()
    configuration.access_token = access_token
    api_client = upstox_client.ApiClient(configuration)
    history_api = upstox_client.HistoryV3Api(api_client)

    all_candles = []

    # 1. Historical candles (previous days up to yesterday)
    hist_to = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    hist_response = history_api.get_historical_candle_data1(
        instrument_key=instrument_key,
        unit=unit,
        interval=iv,
        to_date=hist_to,
        from_date=from_date,
    )
    if hist_response.data and hist_response.data.candles:
        all_candles.extend(hist_response.data.candles)

    # 2. Today's intraday candles (live, current session)
    try:
        intra_response = history_api.get_intra_day_candle_data(
            instrument_key=instrument_key,
            unit=unit,
            interval=iv,
        )
        if intra_response.data and intra_response.data.candles:
            all_candles.extend(intra_response.data.candles)
    except Exception:
        pass  # market may not have opened yet — historical data is sufficient

    if not all_candles:
        raise ValueError(
            f"No data returned for '{symbol}' from Upstox "
            f"({from_date} to {to_date}, interval={interval})."
        )

    df = pd.DataFrame(
        all_candles,
        columns=["datetime", "open", "high", "low", "close", "volume", "oi"],
    )
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime").sort_index()
    df = df[~df.index.duplicated(keep="last")]  # drop overlaps if any
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df


def fetch_ltp(symbols: list[str], access_token: str | None = None) -> dict[str, float]:
    """
    Fetch the Last Traded Price (LTP) for a list of symbols in one API call.

    Returns a dict {symbol: ltp}. Symbols that fail are omitted.
    """
    from tech_analyzer.data.auth import load_token
    from tech_analyzer.data.instruments import symbol_to_instrument_key

    if access_token is None:
        access_token = load_token()
        if access_token is None:
            raise RuntimeError("No Upstox access token. Run: python -m tech_analyzer --auth")

    # Build instrument_key → symbol reverse map
    key_to_symbol: dict[str, str] = {}
    for sym in symbols:
        try:
            key_to_symbol[symbol_to_instrument_key(sym)] = sym
        except Exception:
            pass

    if not key_to_symbol:
        return {}

    instrument_keys = ",".join(key_to_symbol.keys())

    configuration = upstox_client.Configuration()
    configuration.access_token = access_token
    api_client = upstox_client.ApiClient(configuration)
    quote_api = upstox_client.MarketQuoteApi(api_client)

    try:
        response = quote_api.get_ltp(instrument_keys, "2.0")
    except Exception:
        return {}

    result: dict[str, float] = {}
    if response and response.data:
        for key, quote in response.data.items():
            sym = key_to_symbol.get(key)
            if sym and quote.last_price is not None:
                result[sym] = float(quote.last_price)
    return result
