"""Owner decision A (22 Oct 2026): paper positions opened from 23 Oct 2026 pay Upstox's real charges;
older positions keep the old model and are never re-priced."""
from datetime import date

from backtest import momentum_paper as mp
from backtest import paper_rule as pr
from backtest.backtest_engine import REAL_COSTS_FROM, ChargeModel, charges_for, upstox_delivery_2026


def test_cutoff():
    assert REAL_COSTS_FROM == date(2026, 10, 23)
    assert charges_for(date(2026, 10, 22)).brokerage_flat == 0 and charges_for(None).dp_per_sell == 0
    assert charges_for(date(2026, 10, 23)).brokerage_flat == 20 and charges_for(date(2026, 11, 2)).dp_per_sell == 20


def test_paper_pnl_by_entry_day():
    old = pr.net_pnl(1000, 1050, 20, date(2026, 10, 22))
    assert old == pr.net_pnl(1000, 1050, 20)                       # default = old model (unchanged)
    new = pr.net_pnl(1000, 1050, 20, date(2026, 10, 23))
    assert 70 < old - new < 72                                      # Rs.20 + Rs.20 brokerage + Rs.20 DP + GST


def test_momentum_flat_brokerage_once_per_order():
    prices = {"A": 100.0, "B": 250.0}
    cm = upstox_delivery_2026()
    st = {**mp.initial_state("G"), "as_of": "2026-11-02"}
    s1 = mp.rebalance(st, prices, {"A": 0.5, "B": 0.5}, date(2026, 11, 2), cm=cm)
    spent = sum(q * prices[s] + cm.buy_charges(q * prices[s]) for s, q in s1["units"].items())
    assert abs((st["cash"] - s1["cash"]) - spent) < 0.05            # one order per symbol, not per share
    assert len([t for t in s1["trades"] if t["side"] == "BUY"]) == 2
    s0 = mp.rebalance(st, prices, {"A": 0.5, "B": 0.5}, date(2026, 11, 2), cm=ChargeModel())
    assert s0["units"] and s0["cash"] >= 0                         # old model still works the same way
