from datetime import datetime, timedelta

import yfinance as yf

from config.settings import load_settings

settings = load_settings()
print(f"Garud AI Terminal — mode: {settings.trading_mode.value}")

print("\n--- Diagnostic: raw yfinance data per sector ticker ---")
tickers = {
    "NIFTY": "^NSEI",
    "Banking": "^NSEBANK",
    "IT": "^CNXIT",
    "Pharma": "^CNXPHARMA",
    "Auto": "^CNXAUTO",
    "Metal": "^CNXMETAL",
    "FMCG": "^CNXFMCG",
    "Energy": "^CNXENERGY",
    "Realty": "^CNXREALTY",
}

for name, ticker in tickers.items():
    try:
        df = yf.Ticker(ticker).history(period="1mo")
        df = df.dropna(subset=["Close"])
        if len(df) >= 2:
            first = df["Close"].iloc[0]
            last = df["Close"].iloc[-1]
            print(f"{name} ({ticker}): {len(df)} rows, first={first:.2f} last={last:.2f}")
        else:
            print(f"{name} ({ticker}): only {len(df)} row(s) — NOT ENOUGH DATA")
    except Exception as e:
        print(f"{name} ({ticker}): FAILED — {e}")
