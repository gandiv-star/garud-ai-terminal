from portfolio.correlation_engine import CorrelationEngine

print("--- Verify: real correlation between HDFCBANK and ICICIBANK (both banking) ---")
try:
    ce = CorrelationEngine()
    result = ce.pairwise_correlation("HDFCBANK", "ICICIBANK", lookback_days=60)
    print(f"Correlation: {result.correlation}")
    print("(Two large banks are usually correlated ~0.5 to 0.9 — a number near 0 or negative would be suspicious)")

    print("\n--- Verify: correlation between HDFCBANK and an unrelated sector (SUNPHARMA) ---")
    result2 = ce.pairwise_correlation("HDFCBANK", "SUNPHARMA", lookback_days=60)
    print(f"Correlation: {result2.correlation}")
    print("(Usually lower than the banking-pair correlation above)")
except Exception as e:
    print(f"FAILED: {e}")
