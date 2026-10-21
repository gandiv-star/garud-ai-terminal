"""Runs the after-tax comparison once (manual GitHub Actions run): M2, G, NIFTY ETF and FD for an
owner with total yearly income up to Rs.12 lakh. Sends the result to Telegram, writes
tax_study.csv and stores a NEW TAX_STUDY event. No orders."""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import momentum200 as m2  # noqa: E402
from backtest import nifty50_history as nh  # noqa: E402
from backtest import rule_report  # noqa: E402
from backtest import tax_study as ts  # noqa: E402
from backtest.run_longterm import send_telegram  # noqa: E402

CANDIDATES = tuple(dict.fromkeys(m2.NIFTY200_TODAY + nh.all_symbols()))


def summary_text(res: dict) -> str:
    lines = [f"🧾 Garud — after-tax return (₹{res['capital']:,.0f}, {res['start']} → {res['end']}, {res['years']} yrs)",
             "Income up to ₹12 lakh: FD / liquid fund tax-free · shares: short-term 20%, long-term 12.5% above ₹1.25L/yr",
             ""]
    for r in res["rows"]:
        mark = "" if "beats_fd_after_tax" not in r else (" ✅" if r["beats_fd_after_tax"] else " ❌")
        lines.append(f"{r['strategy']}{mark}: before tax {r['pre_tax_cagr']}% → after tax {r['after_tax_cagr']}%/yr "
                     f"(not sold at end: {r['kept_cagr']}%) | tax ₹{r['tax_paid']:,.0f} | in hand ₹{r['final_after_tax']:,.0f} "
                     f"| DD {r['max_dd']}%")
    lines += ["", "✅ = beats FD 7% after tax. Today's tax rules applied to all years; M2 uses today's NIFTY 200 "
                  "list (optimistic). Information only — confirm with a CA."]
    return "\n".join(lines)


def main() -> int:
    data, eval_start, errors = m2.load(CANDIDATES, rule_report.BENCHMARK_END, nh.ALIASES)
    res = ts.run(data, eval_start, lambda d: CANDIDATES, nh.members_on)
    with open("tax_study.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "pre_tax_cagr", "after_tax_cagr", "kept_cagr", "tax_paid", "final_after_tax",
                    "max_dd", "trades"])
        for r in res["rows"]:
            w.writerow([r["strategy"], r["pre_tax_cagr"], r["after_tax_cagr"], r["kept_cagr"], r["tax_paid"],
                        r["final_after_tax"], r["max_dd"], r["trades"]])
    text = summary_text(res)
    if errors:
        text += f"\nData notes: {len(errors)} symbol(s) without data — " + ", ".join(list(errors)[:12])
    print(text)
    send_telegram(text)
    if os.getenv("DATABASE_URL", "").startswith("postgres"):
        try:
            from config.settings import load_settings
            from database.db import Database
            from database.models import AuditEvent
            db = Database(load_settings())
            db.connect()
            payload = json.loads(json.dumps({**res, "errors": errors}, default=str))
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="TAX_STUDY",
                                           symbol=None, payload=payload))
            print("Saved to database (TAX_STUDY).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
