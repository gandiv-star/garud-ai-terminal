"""App status logic (no Streamlit needed): health checks and research cards."""
import types
from datetime import datetime

from helpers import IST

import garud_health as gh
import garud_research as gr
from backtest import live_guard


def _run(payload):
    return types.SimpleNamespace(payload=payload, timestamp=datetime(2026, 10, 18, 4, 0, tzinfo=IST))


def test_live_check_uses_what_the_automatic_run_reported():
    off = _run({"live": {"active": False, "reason": "TRADING_MODE is PAPER (needs CONTROLLED_LIVE or LIVE)",
                         "problems": []}})
    c = gh.check_live("PAPER", off)
    assert c.status == gh.OK and c.value == "OFF"
    on = _run({"live": {"active": True, "rules": ["volatility_expansion_rule_v2_nifty50"], "problems": []}})
    assert gh.check_live("PAPER", on).status == gh.WARN and gh.check_live("PAPER", on).value == "ON"
    bad = _run({"live": {"active": False, "reason": "x", "problems": ["LIVE_CAPITAL='abc' is not a number"]}})
    c = gh.check_live("PAPER", bad)
    assert c.status == gh.WARN and "LIVE_CAPITAL" in c.detail


def test_live_check_falls_back_for_old_runs():
    assert gh.check_live("PAPER", _run({})).value == "OFF"
    assert gh.check_live("CONTROLLED_LIVE", None).status == gh.WARN


def test_reported_guard_limits_round_trip():
    reported = {"capital": 50000.0, "max_open": 3, "max_stock_pct": 10.0, "daily_loss_limit": 0.0,
                "monthly_loss_limit": 3000.0}
    assert live_guard.GuardConfig.from_dict(reported).as_dict() == reported


def test_evidence_card_shows_version():
    old = gr.evidence_summary({"mode_has_evidence": False})
    new = gr.evidence_summary({"mode_has_evidence": False, "version": 2, "fill_model": {"name": "gap_aware_v2"}})
    assert dict(old["lines"])["Version"].startswith("v1") and "RS bug" in dict(old["lines"])["Version"]
    assert dict(new["lines"])["Version"].startswith("v2 · fills: gap_aware_v2")
    assert old["verdict"] == "પુરાવો નથી"


def test_live_on_but_bad_setting_is_shown_as_blocked():
    run = _run({"live": {"active": True, "rules": ["volatility_expansion_rule_v2_nifty50"],
                         "problems": ["LIVE_CAPITAL='1,00,000' is not a number"]}})
    c = gh.check_live("CONTROLLED_LIVE", run)
    assert c.status == gh.BAD and "BUY" in c.value and "LIVE_CAPITAL" in c.detail
