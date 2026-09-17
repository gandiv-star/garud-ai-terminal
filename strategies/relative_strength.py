from core.constants import Decision, MarketRegime
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal


class RelativeStrengthStrategy(BaseStrategy):
    name = "relative_strength"
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

        index_position = regime.supporting_features.get("price_vs_sma50_pct", 0.0)
        relative_strength = features.trend_strength - index_position

        if regime.regime in (MarketRegime.CRISIS, MarketRegime.STRONG_BEAR):
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.3,
                rationale=f"Regime {regime.regime.value} too risky for relative-strength entries.",
            )

        if relative_strength > 5:
            confidence = min(relative_strength / 15, 1.0)
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.BUY, confidence=round(confidence, 2),
                rationale=(
                    f"Stock is {relative_strength:.1f} points stronger than NIFTY's own "
                    f"position vs its 50-day average — leading the index."
                ),
            )

        return StrategySignal(
            symbol=symbol, strategy_name=self.name, strategy_version=self.version,
            decision=Decision.NO_TRADE, confidence=0.3,
            rationale="Stock is not meaningfully outperforming the index.",
        )
