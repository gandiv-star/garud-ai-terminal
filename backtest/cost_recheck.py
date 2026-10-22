"""Cost re-check — how much do Upstox's real 2026 delivery charges change Garud's results?

Registered 22 Oct 2026 (audit finding). Until now every backtest and paper P&L used ChargeModel()
with brokerage 0 and no DP charge. Upstox's published equity-delivery charges (22 Oct 2026) are
Rs.20 brokerage per order and Rs.20 + GST DP charge per scrip sold (see
backtest_engine.upstox_delivery_2026). This study changes NOTHING in paper trading; it only reports:
  1. the after-tax comparison (same as TAX_STUDY) under the old model and under Upstox 2026
     charges, at Rs.3 lakh and at Rs.1 lakh (flat charges hurt small accounts more);
  2. the extra cost the closed swing paper trades would have paid.
PASS for a strategy = after-tax CAGR (Upstox 2026 charges) still above the 7% FD.
"""
from backtest import tax_study as ts
from backtest.backtest_engine import ChargeModel, upstox_delivery_2026

VERSION = 1
SCENARIOS = (("Old model (brokerage 0, no DP)", "old", 300000.0),
             ("Upstox 2026 charges", "upstox", 300000.0),
             ("Upstox 2026 charges", "upstox", 100000.0))


def model(name: str) -> ChargeModel:
    return upstox_delivery_2026() if name == "upstox" else ChargeModel()


def paper_extra_cost(closed_trades: list) -> dict:
    """closed_trades: [(entry, exit, qty)] -> extra charges under Upstox 2026 vs the old model."""
    old, new = ChargeModel(), upstox_delivery_2026()
    extra = 0.0
    for entry, exit_, qty in closed_trades:
        extra += (new.buy_charges(entry * qty) + new.sell_charges(exit_ * qty)
                  - old.buy_charges(entry * qty) - old.sell_charges(exit_ * qty))
    n = len(closed_trades)
    return {"trades": n, "extra_total": round(extra, 2), "extra_per_trade": round(extra / n, 2) if n else None}


def run(data, eval_start, candidates_fn, nifty50_members_fn, scenarios=SCENARIOS) -> dict:
    out = []
    for label, name, capital in scenarios:
        res = ts.run(data, eval_start, candidates_fn, nifty50_members_fn, capital=capital, charges=model(name))
        out.append({"label": label, "model": name, "capital": capital, "start": res["start"], "end": res["end"],
                    "rows": res["rows"]})
    verdicts = {}
    for sc in out:
        if sc["model"] != "upstox":
            continue
        for r in sc["rows"][1:]:
            verdicts[f'{r["strategy"]} @ Rs.{sc["capital"]:,.0f}'] = bool(r.get("beats_fd_after_tax"))
    return {"version": VERSION, "registered": "2026-10-22", "scenarios": out, "beats_fd_after_tax": verdicts,
            "start": out[0]["start"] if out else None, "end": out[0]["end"] if out else None,
            "note": "Information only: paper trading, benchmarks and old results are unchanged."}
