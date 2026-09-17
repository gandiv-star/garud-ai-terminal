from core.constants import Decision, MarketRegime
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"
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

        if regime.regime in (MarketRegime.CRISIS, MarketRegime.STRONG_BEAR):
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.3,
                rationale=f"Regime {regime.regime.value} too risky for mean-reversion entries.",
            )

        if features.trend_strength < -6:
            confidence = min(abs(features.trend_strength) / 15, 1.0)
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.BUY, confidence=round(confidence, 2),
                rationale=f"Price {features.trend_strength:.1f}% below SMA20 — oversold, reversion expected.",
            )

        return StrategySignal(
            symbol=symbol, strategy_name=self.name, strategy_version=self.version,
            decision=Decision.NO_TRADE, confidence=0.3,
            rationale="Not sufficiently overextended for mean reversion.",
        )
