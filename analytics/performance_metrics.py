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
    def summarize(self, trades: list) -> PerformanceSummary:
        if not trades:
            return PerformanceSummary(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)

        net_pnls = [t.net_pnl for t in trades]
        gross_pnls = [t.gross_pnl for t in trades]

        wins = [p for p in net_pnls if p > 0]
        losses = [p for p in net_pnls if p <= 0]

        win_rate = len(wins) / len(net_pnls) * 100
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = float("inf") if gross_profit > 0 else 0.0

        expectancy = sum(net_pnls) / len(net_pnls)

        cumulative, peak, max_dd = 0.0, 0.0, 0.0
        for p in net_pnls:
            cumulative += p
            peak = max(peak, cumulative)
            max_dd = max(max_dd, peak - cumulative)
        max_dd_pct = (max_dd / peak * 100) if peak > 0 else 0.0

        return PerformanceSummary(
            net_pnl=round(sum(net_pnls), 2),
            gross_pnl=round(sum(gross_pnls), 2),
            win_rate=round(win_rate, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else float("inf"),
            expectancy=round(expectancy, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            trade_count=len(trades),
        )
