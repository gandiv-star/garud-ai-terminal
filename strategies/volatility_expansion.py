from core.constants import Decision
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal


class VolatilityExpansionStrategy(BaseStrategy):
    name = "volatility_expansion"
    version = "0.1.0"

    def evaluate(
        self, symbol: str, features: FeatureSet, regime: RegimeAssessment
    ) -> StrategySignal:
        raise NotImplementedError
