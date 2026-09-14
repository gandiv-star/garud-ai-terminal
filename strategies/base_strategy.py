from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.constants import Decision
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment


@dataclass
class StrategySignal:
    symbol: str
    strategy_name: str
    strategy_version: str
    decision: Decision
    confidence: float  # 0.0 - 1.0
    rationale: str


class BaseStrategy(ABC):
    name: str = "base"
    version: str = "0.1.0"
    enabled: bool = True

    @abstractmethod
    def evaluate(
        self, symbol: str, features: FeatureSet, regime: RegimeAssessment
    ) -> StrategySignal:
        """Return a single signal for one symbol given current features/regime."""
        raise NotImplementedError
