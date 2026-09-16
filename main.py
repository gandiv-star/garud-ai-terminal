from datetime import datetime, timedelta

import yfinance as yf

print("--- Diagnostic 2: ^CNXAUTO with different fetch methods ---")

ticker = "^CNXAUTO"

print("\nMethod A: period='1mo'")
df_a = yf.Ticker(ticker).history(period="1mo")
print(f"Rows: {len(df_a)}")
print(df_a.tail(3))

print("\nMethod B: period='3mo'")
df_b = yf.Ticker(ticker).history(period="3mo")
print(f"Rows: {len(df_b)}")

print("\nMethod C: explicit start/end (last 30 days)")
end = datetime.now()
start = end - timedelta(days=30)
df_c = yf.Ticker(ticker).history(start=start, end=end)
print(f"Rows: {len(df_c)}")
print(df_c.tail(3))

print("\nMethod D: yf.download with explicit start/end")
df_d = yf.download(ticker, start=start, end=end, progress=False)
print(f"Rows: {len(df_d)}")
print(df_d.tail(3))
