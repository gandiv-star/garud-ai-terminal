"""Engine 1: runs the pre-registered Momentum-200 test once (manual GitHub Actions run), sends the
verdict to Telegram, writes momentum200_yearly.csv and stores a NEW MOMENTUM_200 event. No orders."""
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
from backtest.run_longterm import send_telegram  # noqa: E402

CANDIDATES = tuple(dict.fromkeys(m2.NIFTY200_TODAY + nh.all_symbols()))


def summary_text(res: dict, errors: dict) -> str:
    ok = lambda b: "✅" if b else "❌"  # noqa: E731
    lines = ["🚀 Garud Engine 1 — Momentum 200 (15 years, one Rs.1,00,000 account)",
             f"{res['start']} → {res['end']} ({res['years']} yrs). PASS = CAGR > 7% AND max drawdown ≤ 25%", ""]
    for r in res["rows"]:
        f, dec, l5 = r["full"], r["train"], r["test"]
        line = (f"{r['strategy']}: {f['cagr']}% a year (DD {f['max_dd']}%, Rs.{(f['final'] or 0):,.0f}) "
                f"| decade {dec['cagr']}% | last5 {l5['cagr']}% | trades {r['trades']}")
        v = r.get("verdict")
        if v:
            line += (f"\n   >FD {ok(v['beats_fd'])} | DD≤25% {ok(v['dd_ok'])} → {'🟢 PASS' if v['pass'] else 'not passed'}"
                     f" | beat NIFTY: {'yes' if v.get('beats_nifty') else 'no'}")
        lines.append(line)
    lines += ["", "Yearly %:"]
    years = sorted({y for r in res["rows"] for y in r.get("yearly", {})})
    for r in res["rows"]:
        lines.append(f"{r['strategy'].split()[0]}: " + " ".join(f"{str(y)[2:]}:{r['yearly'].get(y, '-')}" for y in years))
    lines += ["", ("🟢 Worth paper trading: " + ", ".join(res["passed"])) if res["passed"] else "❌ No candidate passed.",
              "⚠️ M1/M2 use today's NIFTY 200 list (survivorship bias) → optimistic. PASS ≠ profitable."]
    if errors:
        lines.append(f"Data notes: {len(errors)} symbol(s) without data — " + ", ".join(list(errors)[:20]))
    return "\n".join(lines)


def main() -> int:
    data, eval_start, errors = m2.load(CANDIDATES, rule_report.BENCHMARK_END, nh.ALIASES)
    res = m2.run(data, eval_start, lambda d: CANDIDATES, nh.members_on)
    years = sorted({y for r in res["rows"] for y in r.get("yearly", {})})
    with open("momentum200_yearly.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "cagr_15y", "maxdd_15y", "cagr_decade", "cagr_last5", "pass"] + years)
        for r in res["rows"]:
            w.writerow([r["strategy"], r["full"]["cagr"], r["full"]["max_dd"], r["train"]["cagr"], r["test"]["cagr"],
                        (r.get("verdict") or {}).get("pass", "")] + [r["yearly"].get(y, "") for y in years])
    text = summary_text(res, errors)
    print(text)
    chunk = ""
    for line in text.split("\n"):
        if len(chunk) + len(line) + 1 > 3800:
            send_telegram(chunk)
            chunk = ""
        chunk += line + "\n"
    if chunk.strip():
        send_telegram(chunk)
    if os.getenv("DATABASE_URL", "").startswith("postgres"):
        try:
            from config.settings import load_settings
            from database.db import Database
            from database.models import AuditEvent
            db = Database(load_settings())
            db.connect()
            payload = json.loads(json.dumps({**res, "errors": errors}, default=str))
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="MOMENTUM_200",
                                           symbol=None, payload=payload))
            print("Saved to database (MOMENTUM_200).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
