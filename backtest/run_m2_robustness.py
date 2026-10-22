"""Runs the pre-registered M2 robustness check once (manual GitHub Actions run), sends the result to
Telegram, writes m2_robustness.csv and stores a NEW M2_ROBUSTNESS event. No orders."""
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import m2_robustness as rb  # noqa: E402
from backtest import momentum200 as m2  # noqa: E402
from backtest import nifty50_history as nh  # noqa: E402
from backtest import rule_report  # noqa: E402
from backtest.run_longterm import send_telegram  # noqa: E402

CANDIDATES = tuple(dict.fromkeys(m2.NIFTY200_TODAY + nh.all_symbols()))


def summary_text(res: dict) -> str:
    ok = lambda b: "✅" if b else "❌"  # noqa: E731
    lines = ["🧪 Garud M2 robustness — does Momentum 200 work beyond 'top 20, monthly'?",
             f"{res['start']} → {res['end']} ({res['years']} yrs) · weak-market switch ON · PASS = CAGR > 7% AND DD ≤ 25%", ""]
    for r in res["rows"]:
        f = r["full"]
        lines.append(f"{ok(r['verdict']['pass'])} {r['strategy']}: {f['cagr']}%/yr, DD {f['max_dd']}% | "
                     f"last5 {r['test']['cagr']}% | Sharpe {r['sharpe']} | Sortino {r['sortino']} | trades {r['trades']}")
    lines += ["", f"{'🟢 ROBUST' if res['robust'] else '⚠️ FRAGILE'}: {res['passed_count']}/6 variants pass "
                  f"(needed {rb.ROBUST_MIN_PASS})"]
    b = res.get("bootstrap") or {}
    if b.get("p_below_fd") is not None:
        lines.append(f"🎲 Bootstrap (M2): chance 15-yr CAGR < FD 7% = {b['p_below_fd']}% · "
                     f"5th percentile {b['cagr_p5']}% · median {b['cagr_median']}%"
                     + (f" · chance of a fall > 25% {b['p_dd_over_25']}%" if b.get("p_dd_over_25") is not None else ""))
    for x in res.get("benchmarks") or []:
        if x["available"]:
            lines.append(f"📏 {x['name']} {x['from']}→{x['to']}: {x['cagr']}%/yr vs M2 {x['m2_cagr_same_period']}%/yr")
        else:
            lines.append(f"📏 {x['name']}: no data")
    lines.append("⚠️ Today's NIFTY 200 list (survivorship bias) → optimistic. Information for the paper decision only.")
    return "\n".join(lines)


def main() -> int:
    data, eval_start, errors = m2.load(CANDIDATES, rule_report.BENCHMARK_END, nh.ALIASES)
    end = datetime.combine(rule_report.BENCHMARK_END, datetime.min.time()) + timedelta(days=1)
    bench = {}
    for label, t in rb.BENCH_TICKERS.items():
        try:
            bench[label] = rb.fetch_series(t, end - timedelta(days=m2.EVAL_DAYS + 10), end)
        except Exception as e:
            print(f"benchmark {t} unavailable: {e}")
            bench[label] = []
    res = rb.run(data, eval_start, lambda d: CANDIDATES, bench)
    with open("m2_robustness.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variant", "cagr", "max_dd", "cagr_last5", "sharpe", "sortino", "trades", "pass"])
        for r in res["rows"]:
            w.writerow([r["strategy"], r["full"]["cagr"], r["full"]["max_dd"], r["test"]["cagr"], r["sharpe"],
                        r["sortino"], r["trades"], r["verdict"]["pass"]])
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
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="M2_ROBUSTNESS",
                                           symbol=None, payload=payload))
            print("Saved to database (M2_ROBUSTNESS).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
