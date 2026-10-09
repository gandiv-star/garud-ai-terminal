"""15-year check of the long-term strategies (point-in-time NIFTY 50), run once.

Pre-registered 9 Oct 2026, before running. Period: 15 years ending BENCHMARK_END.
DECADE = first 10 years (2011-2021, never looked at before); LAST5 = last 5 years (already seen).
F/G (true-list momentum) is a PAPER-TRADE CANDIDATE only if ALL hold:
  1. full 15-year CAGR > FD 7%  and  > NIFTY buy & hold CAGR
  2. full 15-year CAGR/MaxDD > buy & hold's
  3. DECADE CAGR > 7%  and  > buy & hold's DECADE CAGR
Note: FD is kept at 7% for the whole period (actual FD rates were ~6-9%).
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import longterm as lt  # noqa: E402
from backtest import nifty50_history as nh  # noqa: E402
from backtest import rule_report  # noqa: E402
from backtest.run_longterm import send_telegram  # noqa: E402

EVAL_DAYS = 15 * 365 + 4
DECADE_DAYS = 10 * 365 + 2


def verdicts(res: dict) -> dict:
    rows = {r["strategy"][0]: r for r in res["rows"]}
    bh = rows["B"]
    out = {}
    for k in "CDEFG":
        r = rows.get(k)
        if not r:
            continue
        f, dec = r["full"], r["train"]
        c1 = (f["cagr"] or -99) > lt.FD_RATE * 100 and (f["cagr"] or -99) > (bh["full"]["cagr"] or -99)
        c2 = (f["ratio"] or -99) > (bh["full"]["ratio"] or -99)
        c3 = (dec["cagr"] or -99) > lt.FD_RATE * 100 and (dec["cagr"] or -99) > (bh["train"]["cagr"] or -99)
        out[k] = {"c1": c1, "c2": c2, "c3": c3, "candidate": c1 and c2 and c3}
    return out


def summary_text(res: dict, ver: dict, errors: dict) -> str:
    ok = lambda b: "✅" if b else "❌"  # noqa: E731
    lines = ["📈 Garud 15-year check (Rs.1,00,000, true NIFTY 50 list)",
             f"{res['start']} → {res['end']} ({res['years']} yrs) | decade to {res['split']}", ""]
    for r in res["rows"]:
        f, d, l5 = r["full"], r["train"], r["test"]
        lines.append(f"{r['strategy']}: 15y {f['cagr']}% (DD {f['max_dd']}%, Rs.{(f['final'] or 0):,.0f}) "
                     f"| decade {d['cagr']}% | last5 {l5['cagr']}% | trades {r['trades']}")
        v = ver.get(r["strategy"][0])
        if v and r["strategy"][0] in "FG":
            lines.append(f"   >FD&index {ok(v['c1'])} | risk-adj {ok(v['c2'])} | decade {ok(v['c3'])} → "
                         f"{'🟢 PAPER-TRADE CANDIDATE' if v['candidate'] else 'not a candidate'}")
    lines += ["", "Yearly %:"]
    years = sorted({y for r in res["rows"] for y in r["yearly"]})
    for r in res["rows"]:
        if r["strategy"][0] in "ABFG":
            lines.append(f"{r['strategy'][:1]}: " + " ".join(f"{str(y)[2:]}:{r['yearly'].get(y, '-')}" for y in years))
    lines.append("")
    lines.append("D/E = today's list (biased, for comparison). F/G = true list on each date.")
    if errors:
        lines.append(f"Data notes: {len(errors)} missing — " + ", ".join(list(errors)[:20]))
    return "\n".join(lines)


def main() -> int:
    mkt, eval_start, errors = lt.load(nh.all_symbols(), rule_report.BENCHMARK_END, nh.ALIASES, EVAL_DAYS)
    res = lt.run(mkt, eval_start, current=set(nh.CURRENT), members_fn=nh.members_on, train_days=DECADE_DAYS)
    ver = verdicts(res)
    years = sorted({y for r in res["rows"] for y in r["yearly"]})
    with open("longterm15_yearly.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "cagr_15y", "maxdd_15y", "cagr_decade", "cagr_last5", "trades"] + years)
        for r in res["rows"]:
            w.writerow([r["strategy"], r["full"]["cagr"], r["full"]["max_dd"], r["train"]["cagr"],
                        r["test"]["cagr"], r["trades"]] + [r["yearly"].get(y, "") for y in years])
    text = summary_text(res, ver, errors)
    print(text)
    send_telegram(text)
    if os.getenv("DATABASE_URL", "").startswith("postgres"):
        try:
            from config.settings import load_settings
            from database.db import Database
            from database.models import AuditEvent
            db = Database(load_settings())
            db.connect()
            payload = json.loads(json.dumps({**res, "verdicts": ver, "errors": errors,
                                             "registered": "2026-10-09"}, default=str))
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc),
                                           event_type="LONGTERM_15Y", symbol=None, payload=payload))
            print("Saved to database (LONGTERM_15Y).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
