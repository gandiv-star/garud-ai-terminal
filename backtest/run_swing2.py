"""Engine 2: runs the pre-registered Swing 2.0 test once (manual GitHub Actions run), sends the
verdict to Telegram, writes swing2_yearly.csv and stores a NEW SWING2_15Y event. No orders."""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import momentum200 as m2  # noqa: E402
from backtest import nifty50_history as nh  # noqa: E402
from backtest import portfolio15 as pf  # noqa: E402
from backtest import rule_report  # noqa: E402
from backtest import swing2 as s2  # noqa: E402
from backtest.run_longterm import send_telegram  # noqa: E402

CANDIDATES = tuple(dict.fromkeys(m2.NIFTY200_TODAY + nh.all_symbols()))


def summary_text(res: dict, errors: dict) -> str:
    ok = lambda b: "✅" if b else "❌"  # noqa: E731
    lines = ["🔁 Garud Engine 2 — Swing 2.0: buy pullbacks in the strongest stocks (15 yrs, Rs.1,00,000)",
             f"{res['start']} → {res['end']}. PASS = CAGR > 7% AND max drawdown ≤ 25%",
             "W-off = buy in weak market too · W-half = half size in weak market · W-stop = no buys in weak market", ""]
    for r in res["rows"]:
        f = r["full"]
        line = (f"{r['strategy']}: {f['cagr']}% a year (DD {f['max_dd']}%, Rs.{(f['final'] or 0):,.0f}) "
                f"| decade {r['train']['cagr']}% | last5 {r['test']['cagr']}%")
        v, ts = r.get("verdict"), r.get("trade_stats")
        if v:
            line += f"\n   >FD {ok(v['beats_fd'])} | DD≤25% {ok(v['dd_ok'])} → {'🟢 PASS' if v['pass'] else 'not passed'}" \
                    f" | beat NIFTY: {'yes' if v.get('beats_nifty') else 'no'}"
        if ts:
            line += (f"\n   trades {ts['count']} | win {ts['win_rate']}% | PF {ts['pf']} | gap stops {ts['gap_stops']}"
                     f" | weak-market trades {ts['weak_trades']} (net Rs.{ts['weak_net']:,.0f}) | invested {r.get('exposure_pct')}%")
        lines.append(line)
    lines += ["", ("🟢 Chosen for paper trading (S50, best return per drawdown): " + res["chosen"]) if res["chosen"]
              else "❌ No S50 version passed — Engine 2 is not a candidate.",
              "⚠️ S200 rows use today's NIFTY 200 list (optimistic) — information only. PASS ≠ profitable."]
    if errors:
        lines.append(f"Data notes: {len(errors)} symbol(s) without data — " + ", ".join(list(errors)[:15]))
    return "\n".join(lines)


def main() -> int:
    u, mkt, eval_start, errors = pf.load(CANDIDATES, rule_report.BENCHMARK_END, nh.ALIASES)
    res = s2.run(u, mkt, eval_start, {"S50": nh.members_on, "S200": lambda d: CANDIDATES})
    years = sorted({y for r in res["rows"] for y in r.get("yearly", {})})
    with open("swing2_yearly.csv", "w", newline="") as f:
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
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="SWING2_15Y",
                                           symbol=None, payload=payload))
            print("Saved to database (SWING2_15Y).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
