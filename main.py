from datetime import datetime, timedelta

from data.yfinance_loader import YFinanceLoader
from features.feature_engine import FeatureEngine
from regime.regime_engine import RegimeEngine
from strategies.momentum import MomentumStrategy

print("--- Verify: FeatureEngine + MomentumStrategy on RELIANCE ---")
try:
    loader = YFinanceLoader()
    end = datetime.now()
    start = end - timedelta(days=60)
    bars = loader.get_historical_bars("RELIANCE", start, end)
    print(f"Fetched {len(bars)} bars.")

    fe = FeatureEngine()
    features = fe.compute("RELIANCE", bars)
    print(f"Features: trend={features.trend_strength} momentum={features.momentum} "
          f"atr={features.atr} volatility={features.volatility} "
          f"rel_vol={features.relative_volume} gap={features.gap_pct}")

    regime_engine = RegimeEngine()
    regime = regime_engine.detect()
    print(f"Regime: {regime.regime.value}")

    strategy = MomentumStrategy()
    signal = strategy.evaluate("RELIANCE", features, regime)
    print(f"Signal: {signal.decision.value} confidence={signal.confidence}")
    print(f"Rationale: {signal.rationale}")
except Exception as e:
    print(f"FAILED: {e}")
