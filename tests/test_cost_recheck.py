"""Cost re-check — Upstox 2026 charges vs the old model. Synthetic data, no download."""
from backtest import cost_recheck as cr
from backtest.backtest_engine import ChargeModel, upstox_delivery_2026
import garud_research as gr
import test_momentum200 as tm
from backtest import momentum200 as m2


def test_default_model_unchanged():
    cm = ChargeModel()
    assert cm.brokerage_flat == 0 and cm.dp_per_sell == 0
    assert round(cm.sell_charges(100000), 2) == round(100 + 2.97 + 0.1 + 2.97 * 0.18, 2)


def test_upstox_2026_charges():
    u = upstox_delivery_2026()
    buy = u.buy_charges(100000)          # 20 + STT 100 + exch 3.07 + stamp 15 + sebi 0.1 + GST on (20+3.07)
    assert round(buy, 2) == round(20 + 100 + 3.07 + 15 + 0.1 + (20 + 3.07) * 0.18, 2)
    sell = u.sell_charges(100000)        # 20 + STT 100 + exch 3.07 + sebi 0.1 + DP 20 + GST on (20+3.07+20)
    assert round(sell, 2) == round(20 + 100 + 3.07 + 0.1 + 20 + (20 + 3.07 + 20) * 0.18, 2)
    assert round(u.sell_charges(0), 2) == 23.6   # brokerage + GST still per order; no DP without a sale


def test_paper_extra_cost():
    p = cr.paper_extra_cost([(1000.0, 1050.0, 20), (500.0, 480.0, 40)])
    assert p["trades"] == 2 and 70 < p["extra_per_trade"] < 72      # ~Rs.40 brokerage + Rs.20 DP + GST
    assert cr.paper_extra_cost([])["extra_per_trade"] is None


def test_run_old_vs_upstox_and_card():
    data, start, _ = m2.load(tm.SYMS, tm.END, {}, loader=tm.Loader(), nifty=tm._nifty(0.0004), eval_days=900)
    res = cr.run(data, start, lambda d: tm.SYMS, lambda d: frozenset(tm.SYMS))
    old, up3, up1 = res["scenarios"]
    for a, b in zip(old["rows"][1:], up3["rows"][1:]):
        if a["final_after_tax"] and b["final_after_tax"] and a["trades"]:
            assert b["final_after_tax"] <= a["final_after_tax"] + 1     # real charges never help
    assert len(res["beats_fd_after_tax"]) == 6
    card = gr.cost_recheck_summary({**res, "paper": {"trades": 7, "extra_total": 495.6, "extra_per_trade": 70.8}})
    assert "Upstox" in card["title"] and any("Swing paper" in k for k, _ in card["lines"])
    assert "COST_RECHECK" in gr.STUDIES
    from backtest import run_cost_recheck
    assert "Rs.496" in run_cost_recheck.summary_text(res, {"trades": 7, "extra_total": 495.6, "extra_per_trade": 70.8})
