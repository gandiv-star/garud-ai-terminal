from datetime import datetime, timedelta
from data.yfinance_loader import YFinanceLoader

print("--- Verify: Corporate Actions (dividends/splits) ---")
try:
    loader = YFinanceLoader()
    end = datetime.now()
    start = end - timedelta(days=365)

    for symbol in ["RELIANCE", "INFY", "TCS"]:
        print(f"\n{symbol}:")
        events = loader.get_corporate_actions(symbol, start, end)
        if not events:
            print("  No corporate actions in the last 365 days.")
        for e in events:
            print(f"  {e}")
except Exception as e:
    print(f"FAILED: {e}")
