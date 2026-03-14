"""Fetch historical OHLCV data via yfinance for NSE/BSE symbols."""
import yfinance as yf
import pandas as pd


def fetch(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """
    Download historical OHLCV data.

    Args:
        symbol:   NSE symbol with suffix, e.g. 'RELIANCE.NS' or 'TCS.NS'
        period:   yfinance period string — '1d','5d','1mo','3mo','6mo','1y','2y','5y','max'
        interval: yfinance interval — '1m','5m','15m','30m','1h','1d','1wk','1mo'

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    df.index = pd.to_datetime(df.index)
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.columns = df.columns.str.lower()
    return df
