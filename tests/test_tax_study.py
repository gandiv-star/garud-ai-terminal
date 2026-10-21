"""After-tax study — tax arithmetic and synthetic-data run, no download."""
from datetime import date

from backtest import longterm as lt
from backtest import momentum200 as m2
from backtest import tax_study as ts
import garud_research as gr
import test_momentum200 as tm

D0 = date(2020, 5, 1)


def test_short_term_gain_taxed_20pct():
    b = ts.TaxBook()
    b.buy("A", 10, 100.0, D0)
    b.sell("A", 10, 150.0, date(2020, 12, 1))
    assert round(b.settle(), 2) == 100.0          # 500 gain * 20%


def test_long_term_exemption_and_rate():
    b = ts.TaxBook()
    b.buy("A", 1000, 100.0, D0)
    b.sell("A", 500, 300.0, date(2021, 6, 1))      # held > 1 year: 1,00,000 gain -> under 1.25L
    assert b.settle() == 0.0
    b.sell("A", 500, 500.0, date(2022, 6, 1))      # 2,00,000 gain -> 75,000 taxable * 12.5%
    assert round(b.settle(), 2) == 9375.0


def test_fifo_lots_split_short_and_long():
    b = ts.TaxBook()
    b.buy("A", 10, 100.0, D0)
    b.buy("A", 10, 200.0, date(2021, 3, 1))
    b.sell("A", 15, 300.0, date(2021, 6, 1))
    assert round(b.lt, 2) == 2000.0 and round(b.st, 2) == 500.0


def test_short_loss_offsets_long_gain_but_not_reverse():
    b = ts.TaxBook()
    b.st, b.lt = -50000.0, 200000.0
    assert round(b.settle(), 2) == round((150000 - 125000) * 0.125, 2)
    b.st, b.lt = 10000.0, -30000.0                 # long loss cannot reduce the short gain
    assert round(b.settle(), 2) == 2000.0
    assert b.lt_carry == 30000.0
    b.st, b.lt = 0.0, 155000.0                     # carried long loss used next year
    assert b.settle() == 0.0 and b.lt_carry == 0.0


def test_unrealised_tax_on_final_sale():
    b = ts.TaxBook()
    b.buy("A", 10, 100.0, D0)
    assert round(b.unrealised_tax({"A": 200.0}, date(2020, 6, 1)), 2) == 200.0
    assert b.unrealised_tax({"A": 200.0}, date(2022, 6, 1)) == 0.0


def test_untaxed_simulation_matches_engine():
    data, start, _ = m2.load(tm.SYMS, tm.END, {}, loader=tm.Loader(), nifty=tm._nifty(0.0004), eval_days=900)
    mkt = data.mkt
    i0 = max(lt.bisect_right(mkt.dates, start) - 1, 1)
    idx = lt.month_end_indices(mkt.dates, i0)
    a, _ = lt.simulate(mkt, i0, m2.momentum_targets(data, lambda d: tm.SYMS, True), idx)
    b = ts.simulate_taxed(mkt, i0, m2.momentum_targets(data, lambda d: tm.SYMS, True), idx, taxed=False)
    assert [round(v, 6) for _, v in a] == [round(v, 6) for _, v in b["curve"]]
    assert b["tax_paid"] == 0 and b["exit_tax"] == 0


def test_run_rows_and_card():
    data, start, _ = m2.load(tm.SYMS, tm.END, {}, loader=tm.Loader(), nifty=tm._nifty(0.0004), eval_days=900)
    res = ts.run(data, start, lambda d: tm.SYMS, lambda d: frozenset(tm.SYMS))
    names = [r["strategy"] for r in res["rows"]]
    assert names == ["FD 7%", "NIFTY ETF buy & hold", "M2 Momentum 200", "G NIFTY 50 momentum"]
    for r in res["rows"][1:]:
        if r["pre_tax_cagr"] is not None and r["after_tax_cagr"] is not None:
            assert r["after_tax_cagr"] <= r["pre_tax_cagr"] + 0.01
            assert r["tax_paid"] >= 0
        assert isinstance(r["beats_fd_after_tax"], bool)
    card = gr.tax_study_summary(res)
    assert "Tax" in card["title"] and len(card["lines"]) == 5
    assert "TAX_STUDY" in gr.STUDIES
    from backtest import run_tax_study
    text = run_tax_study.summary_text(res)
    assert "after tax" in text and "CA" in text
