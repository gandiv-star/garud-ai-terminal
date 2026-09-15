from dataclasses import dataclass


@dataclass
class PerformanceSummary:
    net_pnl: float
    gross_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    max_drawdown_pct: float
    trade_count: int


class PerformanceCalculator:
    def summarize(self, trades: list[dict]) -> PerformanceSummary:
        raise NotImplementedError
