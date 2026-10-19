"""Phase 2: runs the pre-registered 15-year shared-capital portfolio test once (manual GitHub
Actions run), sends the verdict to Telegram, writes portfolio15_yearly.csv (run Artifacts) and
stores the result as a NEW PORTFOLIO_15Y event (earlier results are never changed). No orders."""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import nifty50_history as nh  # noqa: E402
from backtest import portfolio15 as pf  # noqa: E402
from backtest import rule_report  # noqa: E402
from backtest.run_longterm import send_telegram  # noqa: E402
from strategies.registry import STRATEGY_REGISTRY  # noqa: E402


def summary_text(res: dict, errors: dict) -> str:
    ok = lambda b: "✅" if b else "❌"  # noqa: E731
    lines = ["🏦 Garud Phase 2 — 15-year portfolio test (one Rs.1,00,000 account, true NIFTY 50 list)",
             f"{res['start']} → {res['end']} ({res['years']} yrs). PASS = CAGR > 7% AND max drawdown ≤ 25%", ""]
    for r in res["rows"]:
        f, dec, l5 = r["full"], r["train"], r["test"]
        line = (f"{r['strategy']}: {f['cagr']}% a year (DD {f['max_dd']}%, Rs.{(f['final'] or 0):,.0f}) "
                f"| decade {dec['cagr']}% | last5 {l5['cagr']}%")
        v = r.get("verdict")
        if v:
            line += f"\n   >FD {ok(v['beats_fd'])} | DD≤25% {ok(v['dd_ok'])} → {'🟢 PASS' if v['pass'] else 'not passed'}"
            line += f" | beat NIFTY: {'yes' if v.get('beats_nifty') else 'no'}"
        ts = r.get("trade_stats")
        if ts:
            tw = r.get("two_year") or {}
            line += (f"\n   trades {ts['count']} | win {ts['win_rate']}% | PF {ts['pf']} | gap-down stops "
                     f"{ts['gap_stops']} | money invested {r.get('exposure_pct')}% of the time"
                     f" | 2-yr windows up {tw.get('positive')}/{tw.get('windows')}")
        lines.append(line)
    lines += ["", "Yearly %:"]
    years = sorted({y for r in res["rows"] for y in r.get("yearly", {})})
    for r in res["rows"]:
        lines.append(f"{r['strategy'].split()[0]}: " + " ".join(f"{str(y)[2:]}:{r['yearly'].get(y, '-')}"
                                                                for y in years))
    lines += ["", ("🟢 Paper-trade candidate(s): " + ", ".join(res["passed"])) if res["passed"]
              else "❌ No candidate passed.",
              "ℹ️ C/F/G were already known when the bar was set; A/A2 are new. PASS ≠ profitable — "
              "paper trading decides."]
    if errors:
        lines.append(f"Data notes: {len(errors)} symbol(s) without data — " + ", ".join(list(errors)[:15]))
    return "\n".join(lines)


def main() -> int:
    u, mkt, eval_start, errors = pf.load(nh.all_symbols(), rule_report.BENCHMARK_END, nh.ALIASES)
    res = pf.run(u, mkt, eval_start, nh.members_on, STRATEGY_REGISTRY["Trend Following"], current=nh.CURRENT)
    years = sorted({y for r in res["rows"] for y in r.get("yearly", {})})
    with open("portfolio15_yearly.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "cagr_15y", "maxdd_15y", "cagr_decade", "cagr_last5", "pass"] + years)
        for r in res["rows"]:
            w.writerow([r["strategy"], r["full"]["cagr"], r["full"]["max_dd"], r["train"]["cagr"], r["test"]["cagr"],
                        (r.get("verdict") or {}).get("pass", "")] + [r["yearly"].get(y, "") for y in years])
    text = summary_text(res, errors)
    print(text)
    chunk = ""
    for line in text.split("\n"):            # Telegram allows ~4000 characters per message
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
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="PORTFOLIO_15Y",
                                           symbol=None, payload=payload))
            print("Saved to database (PORTFOLIO_15Y).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
