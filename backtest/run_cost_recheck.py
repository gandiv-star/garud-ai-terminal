"""Runs the cost re-check once (manual GitHub Actions run). Sends the result to Telegram, writes
cost_recheck.csv and stores a NEW COST_RECHECK event. Reads closed paper trades (read-only). No orders."""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import cost_recheck as cr  # noqa: E402
from backtest import momentum200 as m2  # noqa: E402
from backtest import nifty50_history as nh  # noqa: E402
from backtest import rule_report  # noqa: E402
from backtest.run_longterm import send_telegram  # noqa: E402

CANDIDATES = tuple(dict.fromkeys(m2.NIFTY200_TODAY + nh.all_symbols()))


def summary_text(res: dict, paper: dict | None) -> str:
    lines = [f"💸 Garud cost re-check — Upstox 2026 delivery charges (Rs.20/order + DP Rs.20+GST per sell)",
             f"{res['start']} → {res['end']} · after tax (income up to Rs.12 lakh) · old results unchanged", ""]
    for sc in res["scenarios"]:
        lines.append(f"▶ {sc['label']} · Rs.{sc['capital']:,.0f}")
        for r in sc["rows"][1:]:
            mark = " ✅" if r.get("beats_fd_after_tax") else " ❌"
            lines.append(f"  {r['strategy']}{mark}: after tax {r['after_tax_cagr']}%/yr | tax Rs.{r['tax_paid']:,.0f} "
                         f"| in hand Rs.{r['final_after_tax']:,.0f} | trades {r['trades']}")
    if paper and paper.get("trades"):
        lines += ["", f"Swing paper trades closed so far: {paper['trades']} → Upstox charges would add "
                      f"Rs.{paper['extra_total']:,.0f} (≈ Rs.{paper['extra_per_trade']:,.0f} per trade)"]
    lines.append("✅ = still beats FD 7% after tax. Information only — nothing in paper trading was changed.")
    return "\n".join(lines)


def main() -> int:
    data, eval_start, errors = m2.load(CANDIDATES, rule_report.BENCHMARK_END, nh.ALIASES)
    res = cr.run(data, eval_start, lambda d: CANDIDATES, nh.members_on)
    paper, db = None, None
    if os.getenv("DATABASE_URL", "").startswith("postgres"):
        try:
            from backtest import paper_rule
            from config.settings import load_settings
            from database.db import Database
            db = Database(load_settings())
            db.connect()
            closed = [(t.entry_price, t.exit_price, t.quantity) for t in db.get_trades(limit=5000)
                      if t.strategy_name in paper_rule.RULE_IDS and t.exit_price is not None]
            paper = cr.paper_extra_cost(closed)
        except Exception as e:
            print(f"Paper trades unavailable: {e}")
    with open("cost_recheck.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "capital", "strategy", "pre_tax_cagr", "after_tax_cagr", "tax_paid", "final_after_tax", "trades"])
        for sc in res["scenarios"]:
            for r in sc["rows"]:
                w.writerow([sc["label"], sc["capital"], r["strategy"], r["pre_tax_cagr"], r["after_tax_cagr"],
                            r["tax_paid"], r["final_after_tax"], r["trades"]])
    text = summary_text(res, paper)
    if errors:
        text += f"\nData notes: {len(errors)} symbol(s) without data — " + ", ".join(list(errors)[:12])
    print(text)
    send_telegram(text)
    if db is not None:
        try:
            from database.models import AuditEvent
            payload = json.loads(json.dumps({**res, "paper": paper, "errors": errors}, default=str))
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="COST_RECHECK",
                                           symbol=None, payload=payload))
            print("Saved to database (COST_RECHECK).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
