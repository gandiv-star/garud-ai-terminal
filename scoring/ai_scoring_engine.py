from dataclasses import dataclass, field

from core.constants import Decision
from strategies.base_strategy import StrategySignal


@dataclass
class CandidateScore:
    symbol: str
    score: float
    contributing_factors: dict[str, float] = field(default_factory=dict)
    signals: list[StrategySignal] = field(default_factory=list)


class AIScoringEngine:
    def score(self, symbol: str, signals: list[StrategySignal]) -> CandidateScore:
        # Exclude regime_adaptive: it delegates to another strategy already
        # in this list, so including it would double-count that vote.
        voting_signals = [s for s in signals if s.strategy_name != "regime_adaptive"]

        if not voting_signals:
            return CandidateScore(symbol=symbol, score=50.0, contributing_factors={}, signals=signals)

        weighted_sum = 0.0
        contributing_factors: dict[str, float] = {}
        for sig in voting_signals:
            if sig.decision == Decision.BUY:
                vote = 1.0
            elif sig.decision == Decision.SELL:
                vote = -1.0
            else:
                vote = 0.0
            contribution = vote * sig.confidence
            weighted_sum += contribution
            contributing_factors[sig.strategy_name] = round(contribution, 3)

        net_score = weighted_sum / len(voting_signals)
        score_0_100 = max(0.0, min(100.0, 50 + net_score * 50))

        return CandidateScore(
            symbol=symbol,
            score=round(score_0_100, 1),
            contributing_factors=contributing_factors,
            signals=signals,
        )
