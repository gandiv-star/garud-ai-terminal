"""Automatic run of the NIFTY iron condor PAPER test (backtest/options_paper.py).
Called by .github/workflows/rule_paper_trading.yml after the stock rules. Never places orders.
Telegram: on entries/exits/errors (once per day per content), Friday evening summary,
and always on a manual run (with an Upstox connection check)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import options_paper as op  # noqa: E402
from backtest.run_rule_paper import _first_time_today, send_telegram  # noqa: E402
from config.settings import load_settings  # noqa: E402
from database.db import Database  # noqa: E402


def connection_check(data) -> str:
    try:
        exps, lots = op.expiries_and_lot(data.contracts())
        nxt = [str(e) for e in exps[:3]]
        return f"✅ Upstox data OK — next expiries {', '.join(nxt)} | lot {lots.get(exps[0]) if exps else '?'}"
    except Exception as e:
        return f"❌ Upstox data check failed: {e}"


def main() -> int:
    settings = load_settings()
    if settings.database_url.startswith("sqlite"):
        print("DATABASE_URL is not the hosted database — refusing to run.")
        return 1
    kill = os.getenv("GARUD_KILL_SWITCH", "").strip().upper() in ("ON", "1", "TRUE", "YES")
    manual = os.getenv("RUN_SOURCE", "").strip().lower() == "manual"
    db = Database(settings)
    db.connect()
    now = op._now()
    data = op.UpstoxData()
    try:
        rep = op.run(db, data, now, allow_entries=not kill)
    except Exception as e:
        rep = op.OptReport(errors=[f"options run crashed: {e}"])
    lines = [f"🎯 Garud options paper (NIFTY iron condor) — {now:%Y-%m-%d %H:%M} IST"]
    lines += [ln for ln in rep.lines if manual or not ln.startswith("ℹ️")]
    if rep.errors:
        lines.append("⚠️ " + "; ".join(rep.errors[:6]))
    if manual:
        lines.append(connection_check(data))
    text = "\n".join(lines)
    print(text)
    evening_friday = now.weekday() == 4 and now.time() >= op.MARKET_CLOSE
    if manual:
        send_telegram(text)
    elif rep.activity or rep.errors:
        if _first_time_today(db, "options", now, "\n".join(lines[1:])):
            send_telegram(text)
    elif evening_friday and _first_time_today(db, "options_weekly", now):
        send_telegram(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
