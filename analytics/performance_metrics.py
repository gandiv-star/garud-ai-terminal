import math
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
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0


def _get(trade, key, default=None):
    if isinstance(trade, dict):
        return trade.get(key, default)
    return getattr(trade, key, default)


def _std(values: list) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _downside_std(values: list, target: float = 0.0) -> float:
    downside = [min(0.0, v - target) for v in values]
    if len(downside) < 2:
        return 0.0
    variance = sum(d ** 2 for d in downside) / (len(downside) - 1)
    return math.sqrt(variance)


class PerformanceCalculator:
    def summarize(self, trades: list, starting_capital: float = 100000.0) -> PerformanceSummary:
        if not trades:
            return PerformanceSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0)

        net_pnls = [_get(t, "net_pnl", 0.0) for t in trades]
        gross_pnls = [_get(t, "gross_pnl", _get(t, "net_pnl", 0.0)) for t in trades]

        wins = [p for p in net_pnls if p > 0]
        losses = [p for p in net_pnls if p <= 0]

        net_total = sum(net_pnls)
        gross_total = sum(gross_pnls)
        win_rate = len(wins) / len(trades)
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0

        if losses and sum(losses) != 0:
            profit_factor = sum(wins) / abs(sum(losses))
        elif wins:
            profit_factor = 999.0  # no losses at all — cap instead of infinity
        else:
            profit_factor = 0.0

        expectancy = net_total / len(trades)

        equity = starting_capital
        peak = equity
        max_dd = 0.0
        for p in net_pnls:
            equity += p
            peak = max(peak, equity)
            dd = (peak - equity) / peak * 100 if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

        # Per-trade Sharpe/Sortino — NOT annualized (holding periods vary and
        # aren't reliably known here), risk-free rate assumed 0. These are
        # meant to compare strategies/runs against each other consistently,
        # not as absolute annualized figures comparable to published fund
        # Sharpe ratios.
        returns_pct = [p / starting_capital for p in net_pnls] if starting_capital > 0 else []
        mean_return = sum(returns_pct) / len(returns_pct) if returns_pct else 0.0
        std_return = _std(returns_pct)
        sharpe_ratio = mean_return / std_return if std_return > 0 else 0.0
        downside_std_return = _downside_std(returns_pct)
        sortino_ratio = mean_return / downside_std_return if downside_std_return > 0 else 0.0

        return PerformanceSummary(
            net_pnl=round(net_total, 2),
            gross_pnl=round(gross_total, 2),
            win_rate=round(win_rate, 3),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 3),
            expectancy=round(expectancy, 2),
            max_drawdown_pct=round(max_dd, 2),
            trade_count=len(trades),
            sharpe_ratio=round(sharpe_ratio, 3),
            sortino_ratio=round(sortino_ratio, 3),
        )
