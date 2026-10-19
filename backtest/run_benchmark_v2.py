"""Benchmark v2 for the paper rules: the same 5-year backtest as benchmark v1, but with
gap-aware stop fills and slippage (backtest_engine.FillModel, pre-registered 18 Oct 2026).

Run manually from GitHub Actions ("Rule benchmark v2 (gap-aware fills)").
  * benchmark v1 (legacy fills) is NEVER changed — the pre-registered 10/20/30-trade
    checkpoints keep using it;
  * v2 is stored as extra RULE_BENCHMARK events with "version": 2, only for rules that
    do not have a v2 yet, so re-running cannot overwrite anything;
  * the result goes to Telegram as a v1 vs v2 comparison. No strategy is declared
    profitable by this — it only shows how much the optimistic fills flattered v1.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import paper_rule, rule_report  # noqa: E402
from backtest.backtest_engine import FillModel  # noqa: E402
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


def comparison_text(v1: dict, v2: dict) -> str:
    lines = ["📐 Garud benchmark v2 (gap-aware stops + slippage) vs v1",
             f"Period: {next(iter(v2.values()), {}).get('period', '—')}", ""]
    for rule in paper_rule.RULES:
        a, b = v1.get(rule.rule_id) or {}, v2.get(rule.rule_id) or {}
        lines.append(f"• {rule.title}")
        lines.append(f"  v1: {a.get('trades', '—')} trades | net Rs.{a.get('net', '—')} | PF {a.get('pf', '—')} "
                     f"| avg Rs.{a.get('mean', '—')}")
        lines.append(f"  v2: {b.get('trades', '—')} trades | net Rs.{b.get('net', '—')} | PF {b.get('pf', '—')} "
                     f"| avg Rs.{b.get('mean', '—')} | gap-down stops {b.get('gap_stop_fills', '—')}")
    lines += ["", "ℹ️ v1 remains the yardstick for the pre-registered checkpoints. "
                  "This is a backtest comparison only — not proof of profit."]
    return "\n".join(lines)


def main() -> int:
    if not os.getenv("DATABASE_URL", "").startswith("postgres"):
        print("DATABASE_URL is not the hosted database — refusing to run (results would be lost).")
        return 1
    from config.settings import load_settings
    from database.db import Database
    from database.models import AuditEvent

    db = Database(load_settings())
    db.connect()
    v1 = rule_report.stored_benchmarks(db, rule_report.BENCH_VERSION)
    v2 = rule_report.stored_benchmarks(db, rule_report.BENCH_VERSION_V2)
    missing = [r for r in paper_rule.RULES if r.rule_id not in v2]
    if missing:
        fresh = rule_report.compute_benchmarks(missing, STRATEGY_REGISTRY, fill_model=FillModel(),
                                               version=rule_report.BENCH_VERSION_V2)
        for rid, bench in fresh.items():
            bench["registered"] = "2026-10-18"
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc),
                                           event_type=rule_report.BENCH_EVENT, symbol=None,
                                           payload=json.loads(json.dumps(bench, default=str))))
            v2[rid] = bench
        print(f"Saved benchmark v2 for {len(fresh)} rule(s).")
    else:
        print("Benchmark v2 already stored for every rule — nothing recomputed.")
    text = comparison_text(v1, v2)
    print(text)
    send_telegram(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
