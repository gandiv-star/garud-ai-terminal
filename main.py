from datetime import datetime, timedelta

import yfinance as yf

from portfolio.correlation_engine import CorrelationEngine, _daily_returns

print("--- Diagnostic: how many data points do we actually get? ---")
returns_hdfc = _daily_returns("HDFCBANK", 90)
returns_icici = _daily_returns("ICICIBANK", 90)
print(f"HDFCBANK: {len(returns_hdfc)} daily returns")
print(f"ICICIBANK: {len(returns_icici)} daily returns")

print("\n--- Verify: correlation between HDFCBANK and ICICIBANK (both banking) ---")
ce = CorrelationEngine()
result = ce.pairwise_correlation("HDFCBANK", "ICICIBANK", lookback_days=90)
print(f"Correlation: {result.correlation}")

print("\n--- Verify: correlation between HDFCBANK and SUNPHARMA (unrelated sector) ---")
result2 = ce.pairwise_correlation("HDFCBANK", "SUNPHARMA", lookback_days=90)
print(f"Correlation: {result2.correlation}")

print("\n--- Sanity check: a stock's correlation with ITSELF must be 1.0 ---")
result3 = ce.pairwise_correlation("HDFCBANK", "HDFCBANK", lookback_days=90)
print(f"Self-correlation: {result3.correlation} (must be 1.0 or very close)")
