"""Runs the pre-registered intraday test once: Telegram verdict, intraday_trades.csv artifact,
database event INTRADAY_TEST."""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import intraday_test as it  # noqa: E402
from backtest import paper_rule  # noqa: E402
from backtest.run_longterm import send_telegram  # noqa: E402


def summary_text(res: dict, errors: dict) -> str:
    lines = ["⚡ Garud intraday test (NIFTY 50, 60-min bars, Rs.1,00,000 per trade, real costs)",
             f"{res['first_date']} → {res['last_date']} | halves split {res['split']}", ""]
    for name, r in res["strategies"].items():
        a, h1, h2 = r["all"], r["h1"], r["h2"]
        lines.append(f"{name}: {a['trades']} trades | net Rs.{a['net']:,.0f} | avg Rs.{a['avg']} "
                     f"(before costs Rs.{a['gross_avg']}) | win {a['win']}% | PF {a['pf']}")
        lines.append(f"   1st half PF {h1['pf']} net Rs.{h1['net']:,.0f} | 2nd half PF {h2['pf']} "
                     f"net Rs.{h2['net']:,.0f} → {'🟢 PASS' if r['pass'] else '❌ fail'}")
    passed = [n for n, r in res["strategies"].items() if r["pass"]]
    lines.append("")
    lines.append(f"VERDICT: {'🟢 ' + ', '.join(passed) + ' passed — next: forward paper test' if passed else '❌ no intraday strategy passed'}")
    if not any(r["all"]["trades"] for r in res["strategies"].values()):
        lines.append("⚠️ 0 trades — no usable 09:15 sessions in the data; result not valid, check bar times")
    if errors:
        lines.append(f"Data notes: {len(errors)} — " + ", ".join(list(errors)[:15]))
    return "\n".join(lines)


def main() -> int:
    end = datetime.now(timezone.utc).replace(tzinfo=None)
    trades, errors = it.collect(paper_rule.UNIVERSE_NIFTY50, end,
                                progress=lambda i, n, s: print(f"[{i}/{n}] {s}", flush=True))
    res = it.analyse(trades)
    with open("intraday_trades.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["strategy", "symbol", "date", "side", "entry", "exit",
                                          "reason", "gross", "net"])
        w.writeheader()
        w.writerows(trades)
    text = summary_text(res, errors)
    print(text)
    send_telegram(text)
    if os.getenv("DATABASE_URL", "").startswith("postgres"):
        try:
            from config.settings import load_settings
            from database.db import Database
            from database.models import AuditEvent
            db = Database(load_settings())
            db.connect()
            payload = json.loads(json.dumps({**res, "errors": errors, "registered": "2026-10-15"}, default=str))
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="INTRADAY_TEST",
                                           symbol=None, payload=payload))
            print("Saved to database (INTRADAY_TEST).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
