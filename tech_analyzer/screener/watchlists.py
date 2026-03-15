"""Built-in watchlists and file-based watchlist loader."""

# Nifty 50 constituents (NSE tickers with .NS suffix)
NIFTY50: list[str] = [
    "ADANIENT.NS",
    "ADANIPORTS.NS",
    "APOLLOHOSP.NS",
    "ASIANPAINT.NS",
    "AXISBANK.NS",
    "BAJAJ-AUTO.NS",
    "BAJFINANCE.NS",
    "BAJAJFINSV.NS",
    "BEL.NS",
    "BPCL.NS",
    "BHARTIARTL.NS",
    "BRITANNIA.NS",
    "CIPLA.NS",
    "COALINDIA.NS",
    "DIVISLAB.NS",
    "DRREDDY.NS",
    "EICHERMOT.NS",
    "GRASIM.NS",
    "HCLTECH.NS",
    "HDFCBANK.NS",
    "HDFCLIFE.NS",
    "HEROMOTOCO.NS",
    "HINDALCO.NS",
    "HINDUNILVR.NS",
    "ICICIBANK.NS",
    "INDUSINDBK.NS",
    "INFY.NS",
    "ITC.NS",
    "JIOFIN.NS",
    "JSWSTEEL.NS",
    "KOTAKBANK.NS",
    "LT.NS",
    "M&M.NS",
    "MARUTI.NS",
    "NESTLEIND.NS",
    "NTPC.NS",
    "ONGC.NS",
    "POWERGRID.NS",
    "RELIANCE.NS",
    "SBILIFE.NS",
    "SBIN.NS",
    "SHRIRAMFIN.NS",
    "SUNPHARMA.NS",
    "TATACONSUM.NS",
    "TATAMOTORS.NS",
    "TATASTEEL.NS",
    "TCS.NS",
    "TECHM.NS",
    "TITAN.NS",
    "ULTRACEMCO.NS",
    "WIPRO.NS",
]

# Nifty Bank constituents
NIFTY_BANK: list[str] = [
    "AUBANK.NS",
    "AXISBANK.NS",
    "BANDHANBNK.NS",
    "FEDERALBNK.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "IDFCFIRSTB.NS",
    "INDUSINDBK.NS",
    "KOTAKBANK.NS",
    "PNB.NS",
    "SBIN.NS",
    "YESBANK.NS",
]

BUILTIN: dict[str, list[str]] = {
    "nifty50": NIFTY50,
    "nifty_bank": NIFTY_BANK,
}


def load(name_or_path: str) -> list[str]:
    """
    Load a watchlist by built-in name or file path.

    Built-in names: 'nifty50', 'nifty_bank'
    File format: one ticker per line, lines starting with '#' are ignored.
    """
    if name_or_path in BUILTIN:
        return BUILTIN[name_or_path]

    with open(name_or_path) as f:
        symbols = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]
    if not symbols:
        raise ValueError(f"No symbols found in '{name_or_path}'.")
    return symbols
