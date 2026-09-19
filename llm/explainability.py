from dataclasses import dataclass

from core.constants import Decision, MarketRegime
from scoring.ai_scoring_engine import CandidateScore


@dataclass
class TradeExplanation:
    symbol: str
    decision: Decision
    ai_score: float
    regime: MarketRegime
    sector: str
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    risk_amount: float | None
    quantity: int | None
    reason: str


class ExplainabilityEngine:
    def explain(
        self,
        symbol: str,
        decision: Decision,
        candidate_score: CandidateScore,
        regime,
        sector: str = "Unknown",
        entry_price: float | None = None,
        stop_price: float | None = None,
        target_price: float | None = None,
        quantity: int | None = None,
    ) -> TradeExplanation:
        risk_amount = None
        if entry_price is not None and stop_price is not None and quantity is not None:
            risk_amount = round(abs(entry_price - stop_price) * quantity, 2)

        voting_signals = [s for s in candidate_score.signals if s.strategy_name != "regime_adaptive"]
        supporting = [s for s in voting_signals if s.decision == decision]

        if supporting:
            strategy_names = ", ".join(s.strategy_name for s in supporting)
            reason = (
                f"{len(supporting)} of {len(voting_signals)} strategies ({strategy_names}) "
                f"voted {decision.value} under a {regime.regime.value} regime. "
                f"{supporting[0].rationale}"
            )
        else:
            reason = (
                f"No strategy voted {decision.value}; composite score was "
                f"{candidate_score.score}/100 under a {regime.regime.value} regime."
            )

        return TradeExplanation(
            symbol=symbol,
            decision=decision,
            ai_score=candidate_score.score,
            regime=regime.regime,
            sector=sector,
            entry_price=round(entry_price, 2) if entry_price is not None else None,
            stop_price=round(stop_price, 2) if stop_price is not None else None,
            target_price=round(target_price, 2) if target_price is not None else None,
            risk_amount=risk_amount,
            quantity=quantity,
            reason=reason,
        )
