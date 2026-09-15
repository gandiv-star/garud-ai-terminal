from dataclasses import dataclass


@dataclass
class CorrelationCheck:
    symbol_a: str
    symbol_b: str
    correlation: float  # -1.0 to 1.0


class CorrelationEngine:
    def pairwise_correlation(self, symbol_a: str, symbol_b: str, lookback_days: int = 60) -> CorrelationCheck:
        raise NotImplementedError

    def max_correlation_with_open_positions(self, symbol: str, open_symbols: list[str]) -> float:
        raise NotImplementedError
