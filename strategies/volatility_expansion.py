from core.constants import Decision, MarketRegime
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal


class VolatilityExpansionStrategy(BaseStrategy):
    name = "volatility_expansion"
    version = "0.1.0"

    def evaluate(
        self, symbol: str, features: FeatureSet, regime: RegimeAssessment
    ) -> StrategySignal:
        if features.atr is None or features.price is None or features.momentum is None:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.0,
                rationale="Insufficient data to compute features.",
            )

        atr_pct = features.atr / features.price * 100

        if regime.regime == MarketRegime.CRISIS:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.3,
                rationale="Crisis regime — volatility already extreme, sitting out.",
            )

        if atr_pct > 2.5 and features.momentum > 1:
            confidence = min(atr_pct / 6, 1.0)
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.BUY, confidence=round(confidence, 2),
                rationale=(
                    f"ATR is {atr_pct:.1f}% of price with positive momentum — "
                    f"possible volatility expansion in favor of the move."
                ),
            )

        return StrategySignal(
            symbol=symbol, strategy_name=self.name, strategy_version=self.version,
            decision=Decision.NO_TRADE, confidence=0.3,
            rationale="No clear volatility expansion signal.",
        )
