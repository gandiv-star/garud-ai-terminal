"""Tools-tab research modules (previously untested): Monte Carlo, bootstrap, walk-forward, correlation."""
from datetime import datetime

from backtest.bootstrap import bootstrap_trades
from backtest.monte_carlo import MonteCarloSimulator
from backtest.walk_forward import WalkForwardValidator
from portfolio import correlation_engine as ce

PNLS = [500.0, -300.0, 200.0, -100.0, 800.0, -600.0, 150.0]


def test_monte_carlo_reorders_only():
    r = MonteCarloSimulator().run(PNLS, iterations=300, seed=1)
    assert r.pct_profitable == 100.0                       # same trades, same total (+650)
    assert r.median_final_pnl == r.p5_final_pnl == r.p95_final_pnl == 650.0
    assert 0 <= r.median_max_drawdown_pct <= r.worst_max_drawdown_pct
    assert MonteCarloSimulator().run(PNLS, iterations=300, seed=1) == r      # reproducible
    assert MonteCarloSimulator().run([]).iterations == 0


def test_bootstrap_varies_and_is_ordered():
    r = bootstrap_trades(PNLS, iterations=500, seed=3)
    assert r.trades_per_path == len(PNLS) and 0 < r.pct_profitable < 100
    assert r.p5_final_pnl <= r.median_final_pnl <= r.p95_final_pnl
    assert r.median_max_drawdown_pct <= r.p95_max_drawdown_pct
    assert bootstrap_trades(PNLS, iterations=500, seed=3) == r
    assert bootstrap_trades([10.0, 20.0], iterations=50).pct_profitable == 100.0


def test_walk_forward_windows_do_not_overlap():
    v = WalkForwardValidator()
    w = v.generate_windows(datetime(2020, 1, 1), datetime(2021, 1, 1), oos_days=90)
    assert len(w) == 4
    assert all(a.out_of_sample_end == b.train_start for a, b in zip(w, w[1:]))
    assert w[-1].out_of_sample_end <= datetime(2021, 1, 1)

    class Res:
        trade_count, net_pnl = 3, 120.0

    class Engine:
        def __init__(self):
            self.calls = []

        def run(self, sym, a, b, capital, strategy):
            self.calls.append((a, b))
            return Res()
    e = Engine()
    out = v.run("INFY", object(), e, w)
    assert len(out) == 4 and e.calls[0] == (w[0].validation_end, w[0].out_of_sample_end)


def test_correlation_maths(monkeypatch=None):
    series = {"A": [0.01, -0.02, 0.03, 0.0, 0.01, -0.01], "B": [0.02, -0.04, 0.06, 0.0, 0.02, -0.02],
              "C": [-0.01, 0.02, -0.03, 0.0, -0.01, 0.01], "D": [0.01, 0.02]}
    old = ce._daily_returns
    ce._daily_returns = lambda s, d: series[s]
    try:
        eng = ce.CorrelationEngine()
        assert eng.pairwise_correlation("A", "B").correlation == 1.0
        assert eng.pairwise_correlation("A", "C").correlation == -1.0
        assert eng.pairwise_correlation("A", "D").correlation == 0.0          # too short -> 0
        assert eng.max_correlation_with_open_positions("A", ["B", "C"]) == 1.0
        assert eng.max_correlation_with_open_positions("A", []) == 0.0
    finally:
        ce._daily_returns = old
