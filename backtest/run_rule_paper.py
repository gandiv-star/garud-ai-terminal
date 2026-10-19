"""Automated daily run of the pre-registered paper-trading rules.

Run by .github/workflows/rule_paper_trading.yml on weekdays. Writes entries and
exits to the hosted database (DATABASE_URL) and sends a Telegram summary when
TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set. Safe to run any number of times:
every write is idempotent.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import live_executor, paper_rule, rule_report, sandbox_mirror, scanner, trading_mode  # noqa: E402
from config.settings import load_settings  # noqa: E402
from database.db import Database  # noqa: E402
from database.models import AuditEvent  # noqa: E402
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


def _first_time_today(db, kind: str, now, body: str = "") -> bool:
    """True (and remembered) the first time this kind/content is seen today, so repeated
    or delayed runs don't flood Telegram with identical messages."""
    key = hashlib.sha256(body.encode()).hexdigest()[:16]
    today = str(now.date())
    try:
        for ev in db.get_audit_events("TELEGRAM_SENT", limit=300):
            p = ev.payload or {}
            if p.get("date") == today and p.get("kind") == kind and p.get("hash") == key:
                return False
        db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="TELEGRAM_SENT",
                                       symbol=None, payload={"date": today, "kind": kind, "hash": key}))
    except Exception as e:
        print(f"Telegram de-duplication unavailable ({e}) — sending anyway")
    return True


def today_mode(db, kill_switch: bool):
    """Today's trading mode (backtest/trading_mode.py); stored once per day as TRADING_MODE."""
    try:
        now = paper_rule.now_ist()
        nifty = paper_rule.MarketData(now).nifty_completed()
        m = trading_mode.decide([c for _, c in nifty], nifty[-1][0] if nifty else None, paper_rule.RULES,
                                kill_switch, now)
        today = str(now.date())
        last = db.get_audit_events("TRADING_MODE", limit=1)
        p = (last[0].payload or {}) if last else {}
        if p.get("day") != today or p.get("mode") != m["mode"]:
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="TRADING_MODE",
                                           symbol=None, payload=json.loads(json.dumps({**m, "day": today}, default=str))))
        return m
    except Exception as e:
        print(f"Trading mode unavailable: {e}")
        return None


def daily_scan(db, trades: list, now, manual: bool):
    """Evening (or manual) scanner snapshot, stored once per day as SCAN_SNAPSHOT."""
    if not (manual or now.time() >= paper_rule.MARKET_CLOSE_IST):
        return None
    try:
        last = db.get_audit_events("SCAN_SNAPSHOT", limit=1)
        if last and (last[0].payload or {}).get("day") == str(now.date()) and not manual:
            return None
        rule_trades = [t for t in trades if t.strategy_name in paper_rule.RULE_IDS]
        snap = scanner.build_snapshot(paper_rule.MarketData(now), STRATEGY_REGISTRY, rule_trades)
        snap["day"] = str(now.date())
        snap["built_at"] = now.isoformat(timespec="minutes")
        db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="SCAN_SNAPSHOT",
                                       symbol=None, payload=json.loads(json.dumps(snap, default=str))))
        return snap
    except Exception as e:
        print(f"Scanner snapshot failed: {e}")
        return None


def main() -> int:
    settings = load_settings()
    if settings.database_url.startswith("sqlite"):
        print("DATABASE_URL is not set to the hosted database — refusing to run (trades would be lost).")
        return 1

    kill_switch = os.getenv("GARUD_KILL_SWITCH", "").strip().upper() in ("ON", "1", "TRUE", "YES")

    db = Database(settings)
    db.connect()
    report = paper_rule.run_all(db, STRATEGY_REGISTRY, allow_entries=not kill_switch)

    trades = db.get_trades(limit=5000)
    mirror = sandbox_mirror.mirror(db, trades, due_exits=report.due_time_exits, allow_entries=not kill_switch)
    live = live_executor.execute(db, trades, due_exits=report.due_time_exits, allow_entries=not kill_switch)
    lines = [f"🦅 Garud rule paper trading — {report.started}"]
    mode = today_mode(db, kill_switch)
    if mode:
        lines.append(f"🧭 Mode {mode['mode']} (NIFTY {mode['regime']}, {mode['version']})")
    lines += [f"🟢 {e}" for e in report.entries] or []
    lines += [f"🔴 {x}" for x in report.exits] or []
    for rule in paper_rule.RULES:
        s = paper_rule.rule_stats(rule, trades)
        lines.append(f"📊 {rule.title}: closed {s['closed']}/{rule.target_trades}, open {s['open']}, "
                     f"net Rs.{s['net_pnl']}" + (f", PF {s['profit_factor']}" if s["profit_factor"] else ""))
    lines += [f"ℹ️ {n}" for n in report.notes if "outside market hours" not in n]
    if report.due_time_exits:
        lines.append(f"⏰ {len(report.due_time_exits)} time exit(s) due at today's close — broker SELL sent before close")
    if report.errors:
        lines.append(f"⚠️ {len(report.errors)} data issue(s): " + "; ".join(report.errors[:8]))
    lines += [f"🧪 Sandbox order: {p}" for p in mirror.placed]
    lines += [f"🧪❌ Sandbox failed: {f}" for f in mirror.failed[:8]]
    lines += [f"🧪 {n}" for n in mirror.notes]
    lines += [f"💰 {a}" for a in live.actions]
    lines += [f"💰❌ {e}" for e in live.errors[:8]]
    lines += [f"💰 {n}" for n in live.notes if not n.startswith("Live trading OFF")]
    try:
        live_status = live_executor.effective_status()
    except Exception as e:
        live_status = {"active": False, "problems": [f"status unavailable: {type(e).__name__}"]}
    if live_status.get("problems") and not any("blocked until fixed" in n for n in live.notes):
        lines.append("🛡 Live limit setting problem (new live BUYs would be blocked): "
                     + "; ".join(live_status["problems"]))
    if mirror.unreconciled:
        lines.append(f"🧪⚠️ {len(mirror.unreconciled)} unreconciled: " + "; ".join(mirror.unreconciled[:5]))

    now_ist = paper_rule.now_ist()
    snap = daily_scan(db, trades, now_ist, os.getenv("RUN_SOURCE", "").strip().lower() == "manual")
    if snap:
        cands = [r["symbol"] for r in snap["rows"] if r["action"] == "BUY CANDIDATE"]
        lines.append(f"🔎 Scanner ({snap['data_date']}): " + (", ".join(cands) + " — paper entry at next open"
                                                            if cands else "no new candidates"))
    text = "\n".join(lines)
    print(text)
    # Heartbeat for the app's System Health screen (never contains secrets).
    try:
        db.save_audit_event(AuditEvent(
            timestamp=datetime.now(timezone.utc), event_type="PIPELINE_RUN", symbol=None,
            payload={"started": report.started, "source": os.getenv("RUN_SOURCE", ""),
                     "kill_switch": kill_switch, "entries": len(report.entries), "exits": len(report.exits),
                     "errors": [str(e)[:160] for e in report.errors[:5]], "error_count": len(report.errors),
                     "sandbox_failed": len(mirror.failed), "live_errors": len(live.errors),
                     "live": live_status}))
    except Exception as e:
        print(f"Heartbeat not saved: {e}")

    now = paper_rule.now_ist()
    evening = now.time() >= paper_rule.MARKET_CLOSE_IST
    # Runs started by the external scheduler send RUN_SOURCE=scheduler; only a person
    # pressing "Run workflow" (RUN_SOURCE=manual) gets the always-send behaviour.
    manual = os.getenv("RUN_SOURCE", "").strip().lower() == "manual"
    activity = (report.entries or report.exits or report.errors or mirror.placed or mirror.failed
                or live.actions or live.errors or mirror.unreconciled or live_status.get("problems"))

    if manual:
        send_telegram(text)
    elif activity:
        # Same news twice in a day (e.g. a data issue that persists) is sent only once.
        body = "\n".join(lines[1:])
        if _first_time_today(db, "activity", now, body):
            send_telegram(text)
    elif evening and _first_time_today(db, "evening", now):
        send_telegram(text)

    # Weekly report: once on Friday evening (and on every manual run, for checking).
    if manual or (evening and now.weekday() == 4 and _first_time_today(db, "weekly", now)):
        try:
            weekly = rule_report.weekly_report(db, STRATEGY_REGISTRY, now)
        except Exception as e:
            weekly = f"⚠️ Weekly report failed: {e}"
        print(weekly)
        send_telegram(weekly)
    return 0


if __name__ == "__main__":
    sys.exit(main())
