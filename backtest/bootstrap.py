"""Bootstrap Monte Carlo for backtest trades.

Why not just reshuffle? Reshuffling the same trades only changes their ORDER,
so the total P&L is identical in every run — "profitable outcomes" can only
ever be 0% or 100%. Bootstrap instead resamples trades WITH replacement: each
simulated history is a plausible alternative set of trades drawn from the same
behaviour, so the total P&L genuinely varies. That answers the real question:
"given these trades, how likely is this strategy to be profitable at all?"
"""
import random
from dataclasses import dataclass


@dataclass
class BootstrapResult:
    iterations: int
    trades_per_path: int
    pct_profitable: float
    median_final_pnl: float
    p5_final_pnl: float
    p95_final_pnl: float
    median_max_drawdown_pct: float
    p95_max_drawdown_pct: float


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * pct / 100
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _max_drawdown_pct(pnls: list[float], starting_capital: float) -> float:
    equity = peak = starting_capital
    worst = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak * 100)
    return worst


def bootstrap_trades(
    pnls: list[float],
    starting_capital: float = 100000.0,
    iterations: int = 2000,
    seed: int = 42,
) -> BootstrapResult:
    n = len(pnls)
    if n == 0:
        return BootstrapResult(iterations, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    rng = random.Random(seed)
    finals, drawdowns = [], []
    for _ in range(iterations):
        path = [pnls[rng.randrange(n)] for _ in range(n)]
        finals.append(sum(path))
        drawdowns.append(_max_drawdown_pct(path, starting_capital))
    finals.sort()
    drawdowns.sort()
    return BootstrapResult(
        iterations=iterations,
        trades_per_path=n,
        pct_profitable=round(sum(1 for f in finals if f > 0) / iterations * 100, 1),
        median_final_pnl=round(_percentile(finals, 50), 2),
        p5_final_pnl=round(_percentile(finals, 5), 2),
        p95_final_pnl=round(_percentile(finals, 95), 2),
        median_max_drawdown_pct=round(_percentile(drawdowns, 50), 2),
        p95_max_drawdown_pct=round(_percentile(drawdowns, 95), 2),
    )
