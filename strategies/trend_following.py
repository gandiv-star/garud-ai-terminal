from core.constants import Decision, MarketRegime
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal

FAVORABLE_REGIMES = {
    MarketRegime.STRONG_BULL,
    MarketRegime.MODERATE_BULL,
    MarketRegime.WEAK_BULL,
    MarketRegime.SIDEWAYS,
}


class TrendFollowingStrategy(BaseStrategy):
    name = "trend_following"
    version = "0.1.0"

    def evaluate(
        self, symbol: str, features: FeatureSet, regime: RegimeAssessment
    ) -> StrategySignal:
        if features.trend_strength is None:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.0,
                rationale="Insufficient data to compute features.",
            )

        if regime.regime not in FAVORABLE_REGIMES:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.3,
                rationale=f"Regime {regime.regime.value} not suitable for trend following.",
            )

        if features.trend_strength > 1.5:
            confidence = min(features.trend_strength / 10, 1.0)
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.BUY, confidence=round(confidence, 2),
                rationale=f"Price {features.trend_strength:.1f}% above SMA20 in {regime.regime.value} regime — trend intact.",
            )

        if features.trend_strength < -1.5:
            confidence = min(abs(features.trend_strength) / 10, 1.0)
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.SELL, confidence=round(confidence, 2),
                rationale=f"Price {features.trend_strength:.1f}% below SMA20 — trend turning down.",
            )

        return StrategySignal(
            symbol=symbol, strategy_name=self.name, strategy_version=self.version,
            decision=Decision.NO_TRADE, confidence=0.3,
            rationale="Trend not clearly established.",
        )
