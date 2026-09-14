from dataclasses import dataclass, field

from strategies.base_strategy import StrategySignal


@dataclass
class CandidateScore:
    symbol: str
    score: float  # 0-100
    contributing_factors: dict[str, float] = field(default_factory=dict)
    signals: list[StrategySignal] = field(default_factory=list)


class AIScoringEngine:
    def score(self, symbol: str, signals: list[StrategySignal]) -> CandidateScore:
        raise NotImplementedError
