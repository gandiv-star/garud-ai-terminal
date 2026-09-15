from dataclasses import dataclass


@dataclass
class StrategyHealth:
    strategy_name: str
    is_degrading: bool
    recent_win_rate: float
    historical_win_rate: float
    notes: str = ""


class StrategyHealthMonitor:
    def assess(self, strategy_name: str, trades: list[dict]) -> StrategyHealth:
        raise NotImplementedError
