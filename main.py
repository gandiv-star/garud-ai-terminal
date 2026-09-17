from datetime import datetime, timedelta

from data.yfinance_loader import YFinanceLoader
from features.feature_engine import FeatureEngine
from regime.regime_engine import RegimeEngine
from scoring.ai_scoring_engine import AIScoringEngine
from strategies.momentum import MomentumStrategy
from strategies.breakout import BreakoutStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.relative_strength import RelativeStrengthStrategy
from strategies.volume_breakout import VolumeBreakoutStrategy
from strategies.volatility_expansion import VolatilityExpansionStrategy
from strategies.regime_adaptive import RegimeAdaptiveStrategy

print("--- Verify: AIScoringEngine on RELIANCE ---")
try:
    loader = YFinanceLoader()
    end = datetime.now()
    start = end - timedelta(days=60)
    bars = loader.get_historical_bars("RELIANCE", start, end)

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
    signals = [s.evaluate("RELIANCE", features, regime) for s in strategies]

    scorer = AIScoringEngine()
    candidate = scorer.score("RELIANCE", signals)
    print(f"\nAI SCORE: {candidate.score}/100")
    print(f"Contributing factors: {candidate.contributing_factors}")

    # Sanity check: a strong bullish set of signals should score above 50
    print("\n--- Sanity check: manually forced ALL-BUY signals ---")
    from core.constants import Decision
    forced_buy_signals = [
        s.evaluate("RELIANCE", features, regime) for s in strategies
    ]
    for sig in forced_buy_signals:
        sig.decision = Decision.BUY
        sig.confidence = 0.9
    forced_candidate = scorer.score("RELIANCE", forced_buy_signals)
    print(f"All-BUY forced score: {forced_candidate.score}/100 (should be near 100)")
except Exception as e:
    print(f"FAILED: {e}")
