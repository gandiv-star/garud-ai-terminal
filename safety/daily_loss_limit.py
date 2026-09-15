from dataclasses import dataclass


@dataclass
class DailyLossState:
    realized_pnl_pct: float
    unrealized_pnl_pct: float
    limit_pct: float
    triggered: bool = False

    def check(self) -> bool:
        total_pct = self.realized_pnl_pct + self.unrealized_pnl_pct
        self.triggered = total_pct <= -abs(self.limit_pct)
        return self.triggered
