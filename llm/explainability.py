from dataclasses import dataclass

from core.constants import Decision, MarketRegime
from scoring.ai_scoring_engine import CandidateScore


@dataclass
class TradeExplanation:
    symbol: str
    decision: Decision
    score: float
    regime: MarketRegime
    reason: str


class ExplainabilityEngine:
    def explain(
        self, symbol: str, decision: Decision, candidate_score: CandidateScore, regime: MarketRegime
    ) -> TradeExplanation:
        raise NotImplementedError
