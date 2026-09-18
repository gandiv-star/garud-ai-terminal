from dataclasses import dataclass

from portfolio.correlation_engine import CorrelationEngine
from scoring.ai_scoring_engine import CandidateScore


@dataclass
class PortfolioDecision:
    accepted_symbols: list[str]
    rejected_symbols: dict[str, str]


class PortfolioEngine:
    def __init__(self, correlation_engine: CorrelationEngine, max_correlation: float = 0.8):
        self.correlation_engine = correlation_engine
        self.max_correlation = max_correlation

    def select(
        self,
        candidates: list[CandidateScore],
        open_positions: list[str],
        sector_by_symbol: dict[str, str],
        max_sector_exposure_pct: float,
        max_positions_to_add: int | None = None,
    ) -> PortfolioDecision:
        sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)

        accepted: list[str] = []
        rejected: dict[str, str] = {}
        sector_counts: dict[str, int] = {}
        max_per_sector = max(1, round(max_sector_exposure_pct / 10))

        for symbol in open_positions:
            sector = sector_by_symbol.get(symbol, "Unknown")
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        for candidate in sorted_candidates:
            if max_positions_to_add is not None and len(accepted) >= max_positions_to_add:
                rejected[candidate.symbol] = "max_positions_to_add_reached"
                continue

            sector = sector_by_symbol.get(candidate.symbol, "Unknown")
            if sector_counts.get(sector, 0) >= max_per_sector:
                rejected[candidate.symbol] = f"sector_exposure_limit ({sector})"
                continue

            existing = open_positions + accepted
            max_corr = self.correlation_engine.max_correlation_with_open_positions(candidate.symbol, existing)
            if max_corr > self.max_correlation:
                rejected[candidate.symbol] = f"too_correlated (max={max_corr:.2f})"
                continue

            accepted.append(candidate.symbol)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        return PortfolioDecision(accepted_symbols=accepted, rejected_symbols=rejected)
