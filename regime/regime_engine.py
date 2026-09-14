from dataclasses import dataclass, field

from core.constants import MarketRegime, RiskLevel


@dataclass
class RegimeAssessment:
    regime: MarketRegime
    confidence: float  # 0.0 - 1.0
    supporting_features: dict[str, float] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.MODERATE


class RegimeEngine:
    def detect(self, index_symbol: str = "NIFTY") -> RegimeAssessment:
        raise NotImplementedError
