"""Automated daily run of the pre-registered paper-trading rules.

Run by .github/workflows/rule_paper_trading.yml on weekdays. Writes entries and
exits to the hosted database (DATABASE_URL) and sends a Telegram summary when
TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set. Safe to run any number of times:
every write is idempotent.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import paper_rule, rule_report  # noqa: E402
from config.settings import load_settings  # noqa: E402
from database.db import Database  # noqa: E402
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


def main() -> int:
    settings = load_settings()
    if settings.database_url.startswith("sqlite"):
        print("DATABASE_URL is not set to the hosted database — refusing to run (trades would be lost).")
        return 1

    db = Database(settings)
    db.connect()
    report = paper_rule.run_all(db, STRATEGY_REGISTRY)

    trades = db.get_trades(limit=5000)
    lines = [f"🦅 Garud rule paper trading — {report.started}"]
    lines += [f"🟢 {e}" for e in report.entries] or []
    lines += [f"🔴 {x}" for x in report.exits] or []
    for rule in paper_rule.RULES:
        s = paper_rule.rule_stats(rule, trades)
        lines.append(f"📊 {rule.title}: closed {s['closed']}/{rule.target_trades}, open {s['open']}, "
                     f"net Rs.{s['net_pnl']}" + (f", PF {s['profit_factor']}" if s["profit_factor"] else ""))
    lines += [f"ℹ️ {n}" for n in report.notes if "outside market hours" not in n]
    if report.errors:
        lines.append(f"⚠️ {len(report.errors)} data issue(s): " + "; ".join(report.errors[:8]))

    text = "\n".join(lines)
    print(text)

    evening = paper_rule.now_ist().time() >= paper_rule.MARKET_CLOSE_IST
    manual = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
    if report.entries or report.exits or report.errors or evening or manual:
        send_telegram(text)

    # Weekly report: Friday evening run (and every manual run, for checking).
    now = paper_rule.now_ist()
    if (evening and now.weekday() == 4) or manual:
        try:
            weekly = rule_report.weekly_report(db, STRATEGY_REGISTRY, now)
        except Exception as e:
            weekly = f"⚠️ Weekly report failed: {e}"
        print(weekly)
        send_telegram(weekly)
    return 0


if __name__ == "__main__":
    sys.exit(main())
