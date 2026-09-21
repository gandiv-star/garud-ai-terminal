from dataclasses import dataclass


@dataclass
class StrategyHealth:
    strategy_name: str
    is_degrading: bool
    recent_win_rate: float
    historical_win_rate: float
    notes: str = ""


class StrategyHealthMonitor:
    def assess(self, strategy_name: str, trades: list, recent_n: int = 10) -> StrategyHealth:
        if len(trades) < 2:
            return StrategyHealth(strategy_name, False, 0.0, 0.0, "Not enough trades to assess.")

        def win_rate(subset):
            if not subset:
                return 0.0
            wins = sum(1 for t in subset if t.net_pnl > 0)
            return wins / len(subset) * 100

        historical = win_rate(trades)
        recent = win_rate(trades[-recent_n:])
        is_degrading = recent < historical - 15

        notes = (
            f"Recent win rate ({recent:.1f}%) is {historical - recent:.1f}pp below historical ({historical:.1f}%)."
            if is_degrading
            else f"Recent win rate ({recent:.1f}%) is in line with historical ({historical:.1f}%)."
        )
        return StrategyHealth(strategy_name, is_degrading, round(recent, 2), round(historical, 2), notes)
