from core.constants import Decision, MarketRegime
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal

FAVORABLE_REGIMES = {
    MarketRegime.STRONG_BULL,
    MarketRegime.MODERATE_BULL,
    MarketRegime.WEAK_BULL,
}


class MomentumStrategy(BaseStrategy):
    name = "momentum"
    version = "0.1.0"

    def evaluate(
        self, symbol: str, features: FeatureSet, regime: RegimeAssessment
    ) -> StrategySignal:
        if features.trend_strength is None or features.momentum is None:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.0,
                rationale="Insufficient data to compute features.",
            )

        if regime.regime not in FAVORABLE_REGIMES:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.3,
                rationale=f"Regime {regime.regime.value} is not favorable for momentum.",
            )

        if features.trend_strength > 3 and features.momentum > 2:
            confidence = min((features.trend_strength + features.momentum) / 20, 1.0)
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.BUY, confidence=round(confidence, 2),
                rationale=(
                    f"Price {features.trend_strength:.1f}% above SMA20, "
                    f"{features.momentum:.1f}% momentum, in {regime.regime.value} regime."
                ),
            )

        return StrategySignal(
            symbol=symbol, strategy_name=self.name, strategy_version=self.version,
            decision=Decision.NO_TRADE, confidence=0.4,
            rationale="Momentum/trend not strong enough to justify entry.",
        )
