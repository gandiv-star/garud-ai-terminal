"""Runs the paper replay once (manual GitHub Actions run): the real momentum paper engine over the
last ~24 months vs the backtest engine. Sends the result to Telegram and stores a NEW PAPER_REPLAY
event. Writes nothing to the paper portfolios. No orders."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import momentum200 as m2  # noqa: E402
from backtest import nifty50_history as nh  # noqa: E402
from backtest import paper_replay as pr  # noqa: E402
from backtest.run_longterm import send_telegram  # noqa: E402
from backtest.run_momentum_paper import CANDIDATES, decide  # noqa: E402


def summary_text(res: dict) -> str:
    lines = [f"🔁 Garud paper replay — the real paper engine on {res['start']} → {res['end']} ({res['years']} yrs)",
             "Whole shares · paper capital · Upstox 2026 charges · fill at next close · vs backtest engine, same dates", ""]
    for r in res["rows"]:
        lines.append(f"{'✅' if r['engine_ok'] else '⚠️'} {r['portfolio']} Rs.{r['capital']:,.0f}: paper {r['paper_cagr']}%/yr vs "
                     f"backtest {r['backtest_cagr']}%/yr (gap {r['gap_pp']} pp) · DD {r['paper_max_dd']}% vs "
                     f"{r['backtest_max_dd']}% · idle cash {r['avg_idle_cash_pct']}% · {r['paper_trades']} trades · "
                     f"{r['weak_months']}/{r['months']} months in liquid fund · avg monthly diff {r['avg_monthly_diff_pp']} pp")
    lines += ["", f"NIFTY ETF same period: {res['nifty_etf_cagr']}%/yr · FD 7%",
              f"✅ = engine OK (gap ≤ {pr.MAX_GAP_PP} pp/yr and idle cash ≤ {pr.MAX_IDLE_CASH_PCT}%). "
              "This checks the paper ENGINE, not the future market — that is what the forward test from 2 Nov does."]
    return "\n".join(lines)


def main() -> int:
    from backtest import momentum_paper as mp
    today = datetime.now(mp.IST).date()
    data, eval_start, errors = m2.load(CANDIDATES, today, nh.ALIASES, eval_days=pr.REPLAY_DAYS)
    res = pr.run(data, eval_start, decide, lambda d: CANDIDATES, nh.members_on)
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
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="PAPER_REPLAY", symbol=None,
                                           payload=json.loads(json.dumps({**res, "errors": errors}, default=str))))
            print("Saved to database (PAPER_REPLAY).")
        except Exception as e:
            print(f"Database save failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
