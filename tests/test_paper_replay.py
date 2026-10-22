"""Paper replay — the real paper engine vs the backtest engine on synthetic prices (no download)."""
from backtest import momentum200 as m2
from backtest import paper_replay as pr
import garud_research as gr
import test_momentum200 as tm


def _decide(data, pid, i, held):
    if pid == "M2":
        return m2.select(data, i, tm.SYMS, held, weak_switch=True)
    w = m2.g_weights(data.mkt, i, lambda d: frozenset(tm.SYMS))
    return w, set(w)


def _res(nifty_drift=0.0004):
    data, start, _ = m2.load(tm.SYMS, tm.END, {}, loader=tm.Loader(), nifty=tm._nifty(nifty_drift), eval_days=600)
    return pr.run(data, start, _decide, lambda d: tm.SYMS, lambda d: frozenset(tm.SYMS))


def test_paper_engine_tracks_backtest():
    res = _res()
    assert [(r["portfolio"], r["capital"]) for r in res["rows"]] == [("M2", 300000.0), ("G", 100000.0), ("M2", 100000.0)]
    for r in res["rows"]:
        assert r["months"] >= 15 and r["paper_trades"] > 0
        assert r["gap_pp"] is not None and abs(r["gap_pp"]) < 3          # whole shares vs fractions: small gap
        assert r["engine_ok"] == (abs(r["gap_pp"]) <= pr.MAX_GAP_PP and r["avg_idle_cash_pct"] <= pr.MAX_IDLE_CASH_PCT)
    assert res["nifty_etf_cagr"] is not None


def test_weak_market_stays_in_liquid_fund():
    res = _res(-0.0008)                                  # falling NIFTY: weak market every month
    for r in res["rows"]:
        assert r["weak_months"] == r["months"] and r["paper_trades"] == 0
        assert 5.5 < (r["paper_cagr"] or 0) < 7.5          # liquid-fund rate only


def test_card():
    c = gr.paper_replay_summary(_res())
    assert "Paper replay" in c["title"] and len(c["lines"]) == 4
    assert "PAPER_REPLAY" in gr.STUDIES
    from backtest import run_paper_replay as rpr
    assert "engine OK" in rpr.summary_text(_res())
