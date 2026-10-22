"""#97 Charges and P&L — hand-worked examples from the published fee schedules.

Sources (checked 22 Oct 2026): upstox.com/brokerage-charges (equity delivery and NSE options).
These tests prove Garud applies the schedule as written; they do NOT prove the figures match a real
contract note (no contract note available — live trading is OFF). IPFT (≈ Rs.0.10–0.50 per lakh)
and GST on the SEBI fee are not modelled (a few paise per trade)."""
from datetime import date

from backtest import options_paper as op
from backtest import paper_rule as pr
from backtest.backtest_engine import ChargeModel, upstox_delivery_2026

NEW, OLD = date(2026, 10, 23), date(2026, 10, 22)


def close(a, b, tol=0.005):
    return abs(a - b) <= tol


def test_delivery_buy_upstox_2026():
    # Rs.1,00,000 buy: brokerage 20 + STT 100 + NSE 3.07 + stamp 15 + SEBI 0.10 + GST 18% of (20 + 3.07)
    assert close(upstox_delivery_2026().buy_charges(100000), 20 + 100 + 3.07 + 15 + 0.10 + 0.18 * 23.07)


def test_delivery_sell_upstox_2026():
    # Rs.1,00,000 sell: brokerage 20 + STT 100 + NSE 3.07 + SEBI 0.10 + DP 20 + GST 18% of (20 + 3.07 + 20)
    assert close(upstox_delivery_2026().sell_charges(100000), 20 + 100 + 3.07 + 0.10 + 20 + 0.18 * 43.07)


def test_old_model_kept_for_old_positions():
    cm = ChargeModel()
    assert close(cm.buy_charges(100000), 100 + 2.97 + 15 + 0.10 + 0.18 * 2.97)
    assert close(cm.sell_charges(100000), 100 + 2.97 + 0.10 + 0.18 * 2.97)


def test_paper_pnl_is_gross_minus_both_sides():
    entry, exit_, qty = 7088.0, 6728.5, 2
    for day, cm in ((OLD, ChargeModel()), (NEW, upstox_delivery_2026())):
        expect = (exit_ - entry) * qty - cm.buy_charges(entry * qty) - cm.sell_charges(exit_ * qty)
        assert pr.net_pnl(entry, exit_, qty, day) == round(expect, 2)
    # a winning trade smaller than the round-trip charges is a net loss under real charges
    assert pr.net_pnl(1000, 1003, 20, NEW) < 0 < pr.net_pnl(1000, 1003, 20, OLD) + 200


def test_options_leg_2026_rates():
    prem = 2600.0                    # e.g. 40 x 65
    sell = op.leg_charges(prem, True, NEW)
    exp = 20 + prem * 0.0003553 + prem * 0.000001 + prem * 0.0015 + 0.18 * (20 + prem * 0.0003553 + prem * 0.000001)
    assert close(sell, exp)
    buy = op.leg_charges(prem, False, NEW)
    exp = 20 + prem * 0.0003553 + prem * 0.000001 + prem * 0.00003 + 0.18 * (20 + prem * 0.0003553 + prem * 0.000001)
    assert close(buy, exp)


def test_options_old_rates_for_old_condors():
    prem = 2600.0
    assert close(op.leg_charges(prem, True, OLD),
                 20 + prem * 0.0003503 + prem * 0.000001 + prem * 0.001 + 0.18 * (20 + prem * 0.0003503 + prem * 0.000001))
    assert op.leg_charges(prem, True) == op.leg_charges(prem, True, OLD)       # default = old (unchanged)


def test_settlement_stt_on_exercised_longs():
    legs = [{"type": "CE", "strike": 25400, "side": -1}, {"type": "PE", "strike": 24600, "side": -1},
            {"type": "CE", "strike": 25600, "side": 1}, {"type": "PE", "strike": 24400, "side": 1}]
    debit, ch = op.settlement(legs, 25700.0, 65, NEW)
    assert debit == 200.0                                  # short CE 300 in the money, long CE 100
    assert close(ch, 100 * 65 * 0.0015)
    assert close(op.settlement(legs, 25700.0, 65, OLD)[1], 100 * 65 * 0.00125)
