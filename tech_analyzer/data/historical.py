"""Fetch historical OHLCV data via yfinance for NSE/BSE symbols."""
import yfinance as yf
import pandas as pd


def fetch(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """
    Download historical OHLCV data from Yahoo Finance.

    Args:
        symbol:   NSE ticker with suffix, e.g. 'RELIANCE.NS', 'TCS.NS', 'NIFTY50.NS'
                  Use '.NS' for NSE and '.BO' for BSE.
        period:   '1d','5d','1mo','3mo','6mo','1y','2y','5y','max'
        interval: '1m','5m','15m','30m','1h','1d','1wk','1mo'
                  Note: intraday intervals (< 1d) only available for last 60 days.

    Returns:
        DataFrame indexed by datetime with columns: open, high, low, close, volume

    Raises:
        ValueError: if no data is returned for the symbol.
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df.empty:
        raise ValueError(f"No data returned for symbol '{symbol}'. Check the ticker and suffix (.NS/.BO).")

    df.index = pd.to_datetime(df.index)
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.columns = df.columns.str.lower()
    return df
