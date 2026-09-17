from core.constants import Decision, MarketRegime
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal


class VolumeBreakoutStrategy(BaseStrategy):
    name = "volume_breakout"
    version = "0.1.0"

    def evaluate(
        self, symbol: str, features: FeatureSet, regime: RegimeAssessment
    ) -> StrategySignal:
        if features.momentum is None or features.relative_volume is None:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.0,
                rationale="Insufficient data to compute features.",
            )

        if regime.regime == MarketRegime.CRISIS:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.3,
                rationale="Crisis regime — sitting out.",
            )

        price_expanding = features.momentum > 2
        volume_abnormal = features.relative_volume > 1.5

        if price_expanding and volume_abnormal:
            confidence = min(features.momentum / 10 + (features.relative_volume - 1) / 3, 1.0)
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.BUY, confidence=round(confidence, 2),
                rationale=(
                    f"{features.momentum:.1f}% price move on {features.relative_volume:.2f}x "
                    f"average volume — abnormal participation."
                ),
            )

        return StrategySignal(
            symbol=symbol, strategy_name=self.name, strategy_version=self.version,
            decision=Decision.NO_TRADE, confidence=0.3,
            rationale="No combination of price expansion and abnormal volume.",
        )
