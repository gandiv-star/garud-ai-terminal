from datetime import datetime, timedelta

from data.yfinance_loader import YFinanceLoader
from features.feature_engine import FeatureEngine
from regime.regime_engine import RegimeEngine
from strategies.momentum import MomentumStrategy
from strategies.breakout import BreakoutStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.relative_strength import RelativeStrengthStrategy
from strategies.volume_breakout import VolumeBreakoutStrategy
from strategies.volatility_expansion import VolatilityExpansionStrategy
from strategies.regime_adaptive import RegimeAdaptiveStrategy

print("--- Verify: all 8 strategies on RELIANCE ---")
try:
    loader = YFinanceLoader()
    end = datetime.now()
    start = end - timedelta(days=60)
    bars = loader.get_historical_bars("RELIANCE", start, end)
    print(f"Fetched {len(bars)} bars.")

    fe = FeatureEngine()
    features = fe.compute("RELIANCE", bars)

    regime_engine = RegimeEngine()
    regime = regime_engine.detect()
    print(f"Regime: {regime.regime.value}")

    strategies = [
        MomentumStrategy(), BreakoutStrategy(), TrendFollowingStrategy(),
        MeanReversionStrategy(), RelativeStrengthStrategy(), VolumeBreakoutStrategy(),
        VolatilityExpansionStrategy(), RegimeAdaptiveStrategy(),
    ]
    for strat in strategies:
        signal = strat.evaluate("RELIANCE", features, regime)
        print(f"\n{strat.name}: {signal.decision.value} confidence={signal.confidence}")
        print(f"  {signal.rationale}")
except Exception as e:
    print(f"FAILED: {e}")
