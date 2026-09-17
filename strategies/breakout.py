from core.constants import Decision, MarketRegime
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal


class BreakoutStrategy(BaseStrategy):
    name = "breakout"
    version = "0.1.0"

    def evaluate(
        self, symbol: str, features: FeatureSet, regime: RegimeAssessment
    ) -> StrategySignal:
        if features.price is None or features.prior_high_20d is None or features.relative_volume is None:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.0,
                rationale="Insufficient data to compute features.",
            )

        if regime.regime in (MarketRegime.CRISIS, MarketRegime.STRONG_BEAR):
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.3,
                rationale=f"Regime {regime.regime.value} too risky for breakout entries.",
            )

        is_breakout = features.price > features.prior_high_20d
        volume_confirmed = features.relative_volume > 1.3

        if is_breakout and volume_confirmed:
            breakout_pct = (features.price - features.prior_high_20d) / features.prior_high_20d * 100
            confidence = min(0.5 + breakout_pct / 10 + (features.relative_volume - 1) / 4, 1.0)
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.BUY, confidence=round(confidence, 2),
                rationale=(
                    f"Price broke above 20-day high ({features.prior_high_20d:.2f}) "
                    f"by {breakout_pct:.1f}% with {features.relative_volume:.2f}x average volume."
                ),
            )

        if is_breakout and not volume_confirmed:
            return StrategySignal(
                symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                decision=Decision.NO_TRADE, confidence=0.4,
                rationale="Price broke 20-day high but volume did not confirm (needs >1.3x average).",
            )

        return StrategySignal(
            symbol=symbol, strategy_name=self.name, strategy_version=self.version,
            decision=Decision.NO_TRADE, confidence=0.3,
            rationale="No breakout above 20-day high.",
        )
