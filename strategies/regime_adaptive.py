from core.constants import Decision
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal


class RegimeAdaptiveStrategy(BaseStrategy):
    name = "regime_adaptive"
    version = "0.1.0"

    def evaluate(
        self, symbol: str, features: FeatureSet, regime: RegimeAssessment
    ) -> StrategySignal:
        raise NotImplementedError
