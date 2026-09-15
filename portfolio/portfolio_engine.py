from dataclasses import dataclass

from portfolio.correlation_engine import CorrelationEngine
from scoring.ai_scoring_engine import CandidateScore


@dataclass
class PortfolioDecision:
    accepted_symbols: list[str]
    rejected_symbols: dict[str, str]  # symbol -> rejection reason


class PortfolioEngine:
    def __init__(self, correlation_engine: CorrelationEngine):
        self.correlation_engine = correlation_engine

    def select(
        self,
        candidates: list[CandidateScore],
        open_positions: list[str],
        sector_by_symbol: dict[str, str],
        max_sector_exposure_pct: float,
    ) -> PortfolioDecision:
        raise NotImplementedError
