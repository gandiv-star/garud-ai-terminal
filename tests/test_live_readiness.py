"""Live-readiness checklist: never 'ready' while anything is TODO or MANUAL."""
from datetime import date

from backtest import live_readiness as lr


def test_not_ready_today():
    items = lr.checklist({"v2 — NIFTY 50": "collecting data (6/10 for first checkpoint)"}, {"orders_allowed": False,
                         "problems": []}, 0, date(2026, 10, 22))
    st = {n: s for n, s, _ in items}
    assert st["A strategy PASSED its paper test"] == lr.TODO
    assert st["Live switches are OFF until the owner decides"] == lr.OK
    assert st["Static IP server registered with Upstox"] == lr.MANUAL
    assert not lr.ready(items)


def test_problems_and_pass_detected():
    items = lr.checklist({"v3": "✅ VERDICT: PASS on first 30 trades"},
                         {"orders_allowed": True, "problems": ["LIVE_CAPITAL='x' is not a number"]}, 3, date(2026, 10, 1))
    st = {n: (s, d) for n, s, d in items}
    assert st["A strategy PASSED its paper test"] == (lr.OK, "v3")
    assert st["Live switches are OFF until the owner decides"][0] == lr.TODO
    assert "not a number" in st["Live limit variables valid (fail-closed)"][1]
    assert st["Compliance checklist re-checked recently"][0] == lr.OK
    assert not lr.ready(items)                      # MANUAL items keep it from being ready
