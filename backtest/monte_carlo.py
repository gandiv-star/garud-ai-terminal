"""
Monte Carlo trade-order resampling.

Takes the net P&L of each trade a backtest actually produced and
reshuffles the ORDER those same trades occur in, many times, to see
how much the final outcome depends on the lucky/unlucky sequencing of
wins and losses rather than the trades themselves. This does NOT
invent new trades or resample from a distribution — every simulation
uses exactly the same set of real trade outcomes, just reordered.
"""

import random
from dataclasses import dataclass


@dataclass
class MonteCarloResult:
    iterations: int
    pct_profitable: float
    median_final_pnl: float
    p5_final_pnl: float
    p95_final_pnl: float
    median_max_drawdown_pct: float
    worst_max_drawdown_pct: float


class MonteCarloSimulator:
    def run(
        self,
        trade_pnls: list[float],
        starting_capital: float = 100000.0,
        iterations: int = 1000,
        seed: int | None = None,
    ) -> MonteCarloResult:
        if not trade_pnls:
            return MonteCarloResult(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        rng = random.Random(seed)
        final_pnls: list[float] = []
        max_drawdowns: list[float] = []

        for _ in range(iterations):
            shuffled = trade_pnls.copy()
            rng.shuffle(shuffled)
            equity = starting_capital
            peak = equity
            max_dd = 0.0
            for p in shuffled:
                equity += p
                peak = max(peak, equity)
                dd = (peak - equity) / peak * 100 if peak > 0 else 0.0
                max_dd = max(max_dd, dd)
            final_pnls.append(equity - starting_capital)
            max_drawdowns.append(max_dd)

        final_pnls.sort()
        max_drawdowns.sort()
        n = len(final_pnls)

        pct_profitable = sum(1 for p in final_pnls if p > 0) / n * 100
        median_final = final_pnls[n // 2]
        p5_final = final_pnls[max(0, int(n * 0.05) - 1)]
        p95_final = final_pnls[min(n - 1, int(n * 0.95))]
        median_dd = max_drawdowns[n // 2]
        worst_dd = max_drawdowns[-1]

        return MonteCarloResult(
            iterations=iterations,
            pct_profitable=round(pct_profitable, 1),
            median_final_pnl=round(median_final, 2),
            p5_final_pnl=round(p5_final, 2),
            p95_final_pnl=round(p95_final, 2),
            median_max_drawdown_pct=round(median_dd, 2),
            worst_max_drawdown_pct=round(worst_dd, 2),
        )
