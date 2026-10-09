"""Runs the pre-registered long-horizon comparison (FD vs index vs regime ETF vs momentum)
once, sends the verdict to Telegram, writes longterm_yearly.csv (run Artifacts) and
stores the result in the database (event LONGTERM_COMPARISON)."""
import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import longterm as lt  # noqa: E402
from backtest import nifty50_history as nh  # noqa: E402
from backtest import rule_report  # noqa: E402


def send_telegram(text: str) -> None:
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram not configured — skipping message.")
        return
    body = json.dumps({"chat_id": chat_id, "text": text[:4000]}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:
        print(f"Telegram send failed: {e}")


def summary_text(res: dict, errors: dict) -> str:
    lines = ["📈 Garud long-term comparison (Rs.1,00,000)",
             f"{res['start']} → {res['end']} ({res['years']} yrs) | test from {res['split']}", ""]
    for r in res["rows"]:
        f, t = r["full"], r["test"]
        lines.append(f"{r['strategy']}: 5y CAGR {f['cagr']}% (maxDD {f['max_dd']}%, final Rs.{(f['final'] or 0):,.0f}) "
                     f"| test CAGR {t['cagr']}% (maxDD {t['max_dd']}%) | trades {r['trades']}")
        if "candidate" in r:
            lines.append(f"   beats FD: {'✅' if r['beats_fd'] else '❌'} | better than index (CAGR/DD): "
                         f"{'✅' if r['better_than_index'] else '❌'} → "
                         f"{'🟢 PAPER-TRADE CANDIDATE' if r['candidate'] else 'not a candidate'}")
    lines += ["", "Yearly % (calendar):"]
    years = sorted({y for r in res["rows"] for y in r["yearly"]})
    for r in res["rows"]:
        lines.append(f"{r['strategy'][:1]}: " + " | ".join(f"{y}:{r['yearly'].get(y, '-')}" for y in years))
    lines.append("")
    lines.append("⚠️ D/E use today's NIFTY 50 list (survivorship bias) → optimistic. "
                 "F/G use the true list on each date → the honest test.")
    if errors:
        lines.append(f"Data notes: {len(errors)} — " + "; ".join(f"{k}: {v[:60]}" for k, v in list(errors.items())[:8]))
    return "\n".join(lines)


def main() -> int:
    mkt, eval_start, errors = lt.load(nh.all_symbols(), rule_report.BENCHMARK_END, nh.ALIASES)
    res = lt.run(mkt, eval_start, current=set(nh.CURRENT), members_fn=nh.members_on)
    years = sorted({y for r in res["rows"] for y in r["yearly"]})
    with open("longterm_yearly.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "full_cagr", "full_maxdd", "test_cagr", "test_maxdd", "trades"] + years)
        for r in res["rows"]:
            w.writerow([r["strategy"], r["full"]["cagr"], r["full"]["max_dd"], r["test"]["cagr"],
                        r["test"]["max_dd"], r["trades"]] + [r["yearly"].get(y, "") for y in years])
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
            payload = json.loads(json.dumps({**res, "version": 2, "registered": "2026-10-08/09"}, default=str))
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc),
                                           event_type="LONGTERM_COMPARISON", symbol=None, payload=payload))
            print("Saved to database (LONGTERM_COMPARISON).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
