import yfinance as yf

print("--- Diagnostic 3: sector stocks (not indices) ---")

SECTOR_STOCKS = {
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN"],
    "IT": ["TCS", "INFY", "WIPRO"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA"],
    "Auto": ["MARUTI", "TATAMOTORS", "BAJAJ-AUTO"],
    "Metal": ["TATASTEEL", "HINDALCO", "JSWSTEEL"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND"],
    "Energy": ["RELIANCE", "ONGC", "NTPC"],
    "Realty": ["DLF", "GODREJPROP", "OBEROIRLTY"],
}

for sector, stocks in SECTOR_STOCKS.items():
    for stock in stocks:
        try:
            df = yf.Ticker(f"{stock}.NS").history(period="1mo")
            df = df.dropna(subset=["Close"])
            if len(df) >= 2:
                ret = (df["Close"].iloc[-1] - df["Close"].iloc[0]) / df["Close"].iloc[0] * 100
                print(f"{sector} / {stock}: {len(df)} rows, return={ret:.2f}%")
            else:
                print(f"{sector} / {stock}: only {len(df)} row(s) — PROBLEM")
        except Exception as e:
            print(f"{sector} / {stock}: FAILED — {e}")
