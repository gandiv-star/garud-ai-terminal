"""Runs the pre-registered AI/ML Lab test once (manual GitHub Actions run): ML picker vs the M2 rule,
walk-forward, ~10 out-of-sample years. Telegram + NEW ML_LAB event. No orders."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import ml_lab as ml  # noqa: E402
from backtest import momentum200 as m2  # noqa: E402
from backtest import nifty50_history as nh  # noqa: E402
from backtest import rule_report  # noqa: E402
from backtest.run_longterm import send_telegram  # noqa: E402

CANDIDATES = tuple(dict.fromkeys(m2.NIFTY200_TODAY + nh.all_symbols()))


def summary_text(res: dict) -> str:
    if res.get("error"):
        return f"🤖 Garud AI/ML Lab: {res['error']}"
    lines = ["🤖 Garud AI/ML Lab — gradient-boosted trees vs the M2 rule (walk-forward, out-of-sample)",
             f"{res['start']} → {res['end']} ({res['years']} yrs) · {res['months_predicted']} monthly predictions", ""]
    for r in res["rows"]:
        f = r["full"]
        lines.append(f"{r['strategy']}: {f['cagr']}%/yr, DD {f['max_dd']}%, Rs.{(f['final'] or 0):,.0f} "
                     f"| 1st half {r['train']['cagr']}% · 2nd half {r['test']['cagr']}%")
    if res.get("top_quintile_hit_rate") is not None:
        lines.append(f"\nML top-20 beat the average stock in {res['top_quintile_hit_rate']}% of months")
    lines.append(("🟢 ADOPT: the ML picker beat M2 by ≥2%/yr with DD ≤ 25% — candidate for a paper portfolio"
                  if res["adopt_ml"] else
                  "❌ Not adopted: the ML picker did not beat the simple M2 rule by the pre-set margin — M2 stays"))
    lines.append("⚠️ Today's NIFTY 200 list (survivorship bias) for both. Information only.")
    return "\n".join(lines)


def main() -> int:
    data, eval_start, errors = m2.load(CANDIDATES, rule_report.BENCHMARK_END, nh.ALIASES)
    res = ml.run(data, eval_start, lambda d: CANDIDATES)
    text = summary_text(res)
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
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="ML_LAB",
                                           symbol=None, payload=payload))
            print("Saved to database (ML_LAB).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
