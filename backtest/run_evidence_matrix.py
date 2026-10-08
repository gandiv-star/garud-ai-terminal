"""Runs the pre-registered Regime x Strategy evidence matrix once (GitHub Actions,
manual "Run workflow"), sends the verdict to Telegram, writes the full matrix to
evidence_matrix.csv (downloadable from the run's Artifacts) and stores it in the
database (event EVIDENCE_MATRIX) for the future Trading Mode Engine.
"""
import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import evidence_matrix as em  # noqa: E402
from backtest import paper_rule, rule_report  # noqa: E402
from strategies.registry import STRATEGY_REGISTRY  # noqa: E402


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


def summary_text(res: dict) -> str:
    s, b = res["selection_test"], res["baseline_test"]
    lines = [
        "🧠 Garud evidence matrix (Regime × Strategy)",
        f"Train → test split: {res['split_date']} | train {res['train_trades']} trades, test {res['test_trades']}",
        f"Favoured in train: {res['favoured_cells']} cells | confirmed in test: {res['confirmed_cells']}",
        "",
    ]
    for r in res["by_regime"]:
        fav = ", ".join(r["favoured"]) or "none"
        conf = ", ".join(r["confirmed"]) or "none"
        lines.append(f"• {r['regime']}: favoured [{fav}] → confirmed [{conf}]")
    lines += [
        "",
        f"TEST — regime-selected trades: {s['trades']} | net Rs.{s['net']} | PF {s['pf']} | avg Rs.{s['avg']}",
        f"TEST — all trades (baseline): {b['trades']} | net Rs.{b['net']} | PF {b['pf']} | avg Rs.{b['avg']}",
        "",
        ("✅ VERDICT: choosing strategies by regime HAS out-of-sample evidence"
         if res["mode_has_evidence"] else
         "❌ VERDICT: choosing strategies by regime has NO out-of-sample evidence"),
    ]
    return "\n".join(lines)


def main() -> int:
    def progress(d, t, label):
        if d % 50 == 0 or d == t:
            print(f"{d}/{t} {label}", flush=True)

    trades, split = em.collect(paper_rule.UNIVERSE_NIFTY50, STRATEGY_REGISTRY,
                               rule_report.BENCHMARK_END, progress=progress)
    res = em.analyse(trades, split)

    with open("evidence_matrix.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(res["matrix"][0].keys()) if res["matrix"] else ["empty"])
        w.writeheader()
        for row in res["matrix"]:
            w.writerow(row)

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
            payload = {k: v for k, v in res.items()}
            payload["version"] = 1
            payload["registered"] = "2026-10-08"
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="EVIDENCE_MATRIX",
                                           symbol=None, payload=json.loads(json.dumps(payload, default=str))))
            print("Saved to database (EVIDENCE_MATRIX).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
