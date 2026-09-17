from core.constants import Decision, MarketRegime
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal
from strategies.momentum import MomentumStrategy
from strategies.breakout import BreakoutStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy

REGIME_PREFERENCE = {
    MarketRegime.STRONG_BULL: "momentum",
    MarketRegime.MODERATE_BULL: "momentum",
    MarketRegime.WEAK_BULL: "trend_following",
    MarketRegime.SIDEWAYS: "mean_reversion",
}


class RegimeAdaptiveStrategy(BaseStrategy):
    name = "regime_adaptive"
    version = "0.1.0"

    def __init__(self):
        self._sub_strategies = {
            "momentum": MomentumStrategy(),
            "breakout": BreakoutStrategy(),
            "trend_following": TrendFollowingStrategy(),
            "mean_reversion": MeanReversionStrategy(),
        }

    def evaluate(
        self, symbol: str, features: FeatureSet, regime: RegimeAssessment
    ) -> StrategySignal:
        preferred = REGIME_PREFERENCE.get(regime.regime)

        if preferred is None:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.3,
                rationale=f"No strategy preferred for {regime.regime.value} — sitting out.",
            )

        sub_signal = self._sub_strategies[preferred].evaluate(symbol, features, regime)
        return StrategySignal(
            symbol=symbol, strategy_name=self.name, strategy_version=self.version,
            decision=sub_signal.decision, confidence=sub_signal.confidence,
            rationale=f"[Delegated to {preferred}] {sub_signal.rationale}",
        )
