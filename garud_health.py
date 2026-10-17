"""System health for the Garud app — every status comes from a real check, never a
hard-coded tick. Read-only. Used by garud_mobile.py (status bar + 🩺 Health screen)."""
import os
import time as _time
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
APP_VERSION = "2026.10.16-A"
OK, WARN, BAD, NA = "ok", "warn", "bad", "na"


@dataclass
class Check:
    name: str
    status: str          # ok / warn / bad / na
    value: str           # short text for the chip/row
    detail: str = ""


def _ist(ts):
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(IST)


def _age(ts, now) -> str:
    mins = int((now - ts).total_seconds() // 60)
    if mins < 60:
        return f"{max(mins, 0)} મિનિટ પહેલાં"
    if mins < 48 * 60:
        return f"{mins // 60} કલાક પહેલાં"
    return f"{mins // 1440} દિવસ પહેલાં"


def last_session(now: datetime) -> date:
    """Latest weekday session whose daily bar should exist by now (holidays not known)."""
    d = now.date()
    if now.weekday() >= 5 or now.time() < time(9, 15):
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _weekdays_between(a: date, b: date) -> int:
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


# ------------------------------------------------------------------ individual checks
def check_market_data(market: dict | None, now: datetime, error: str = "") -> Check:
    if not market or not market.get("date"):
        return Check("Market data (NIFTY)", BAD, "Unavailable", error or "no NIFTY data")
    d = date.fromisoformat(market["date"])
    gap = _weekdays_between(d, last_session(now))
    if gap == 0:
        return Check("Market data (NIFTY)", OK, f"{d:%d %b}", "છેલ્લો ભાવ સમયસર")
    if gap == 1:
        return Check("Market data (NIFTY)", WARN, f"{d:%d %b}", "1 session જૂનો (રજા હોય તો બરાબર)")
    return Check("Market data (NIFTY)", BAD, f"{d:%d %b}", f"{gap} sessions જૂનો — ડેટા અટક્યો છે")


def check_pipeline(last_run, now: datetime) -> Check:
    if last_run is None:
        return Check("Automatic runs", WARN, "N/A", "હજી heartbeat નોંધાયો નથી (નવા code પછીના પહેલા run થી આવશે)")
    ts, p = _ist(last_run.timestamp), last_run.payload or {}
    gap = _weekdays_between(ts.date(), now.date())
    errs = int(p.get("error_count") or 0)
    status = OK if gap <= 1 else WARN if gap == 2 else BAD
    if errs and status == OK:
        status = WARN
    detail = f"છેલ્લો run {ts:%d %b %H:%M}" + (f" · {errs} data issue(s)" if errs else "")
    return Check("Automatic runs", status, _age(ts, now), detail)


def check_telegram(last_sent, now: datetime) -> Check:
    if last_sent is None:
        return Check("Telegram", NA, "N/A", "હજી કોઈ મોકલાયેલો મેસેજ નોંધાયો નથી")
    ts = _ist(last_sent.timestamp)
    gap = _weekdays_between(ts.date(), now.date())
    return Check("Telegram", OK if gap <= 2 else WARN, _age(ts, now), f"છેલ્લો મેસેજ {ts:%d %b %H:%M}")


def check_tokens(token_event, now: datetime) -> list:
    labels = {"UPSTOX_SANDBOX_TOKEN": "Broker sandbox (Upstox)", "UPSTOX_ANALYTICS_TOKEN": "Options data (Upstox)"}
    if token_event is None:
        return [Check(v, NA, "N/A", "token status હજી નોંધાયું નથી") for v in labels.values()]
    out = []
    for key, label in labels.items():
        info = (token_event.payload or {}).get(key) or {}
        if not info.get("set"):
            out.append(Check(label, BAD, "Not set", "GitHub secret ખૂટે છે"))
            continue
        if not info.get("expires"):
            out.append(Check(label, NA, "Set", "expiry વાંચી શકાઈ નથી"))
            continue
        exp = datetime.fromisoformat(info["expires"])
        days = (exp - now).total_seconds() / 86400
        st = OK if days > 5 else WARN if days > 0 else BAD
        out.append(Check(label, st, f"{max(days, 0):.0f} દિવસ" if days > 0 else "Expired",
                         f"માન્ય {_ist(exp):%d %b %Y} સુધી"))
    return out


def check_ai(env: dict) -> Check:
    if not (env.get("GEMINI_API_KEY") or "").strip():
        return Check("AI (Gemini)", NA, "Unavailable", "GEMINI_API_KEY સેટ નથી — AI સમજૂતી બંધ, બાકી બધું ચાલે")
    return Check("AI (Gemini)", OK, "Configured", "key સેટ છે · 'AI ચકાસો' દબાવી અસલ જવાબ તપાસી શકાય")


def check_live(trading_mode: str) -> Check:
    mode = (trading_mode or "").upper()
    if mode in ("CONTROLLED_LIVE", "LIVE"):
        return Check("Live orders", WARN, mode, "અસલ trading mode — GitHub gates પણ જરૂરી")
    return Check("Live orders", OK, "OFF", f"Mode {mode or 'unset'} — અસલ order જઈ શકે નહીં")


def check_risk(last_run) -> Check:
    p = (last_run.payload or {}) if last_run else {}
    if p.get("kill_switch"):
        return Check("Risk / kill switch", BAD, "KILL SWITCH ON", "નવા trades બંધ (exits ચાલુ)")
    if last_run is None:
        return Check("Risk / kill switch", NA, "N/A", "છેલ્લા run ની માહિતી નથી")
    return Check("Risk / kill switch", OK, "Normal", "Kill switch બંધ · live guard તૈયાર")


def run_db_checks(db_factory, now: datetime) -> dict:
    """One DB round-trip set. Returns {'db': Check, 'last_run', 'last_sent', 'token', 'runs'}."""
    t0 = _time.monotonic()
    try:
        db = db_factory()
        runs = db.get_audit_events("PIPELINE_RUN", limit=20)
        sent = db.get_audit_events("TELEGRAM_SENT", limit=1)
        tok = db.get_audit_events("TOKEN_STATUS", limit=1)
    except Exception as e:
        return {"db": Check("Database", BAD, "Error", str(e)[:160]), "last_run": None, "last_sent": None,
                "token": None, "runs": []}
    ms = int((_time.monotonic() - t0) * 1000)
    return {"db": Check("Database", OK if ms < 5000 else WARN, f"{ms} ms", "Neon Postgres જોડાયેલું"),
            "last_run": runs[0] if runs else None, "last_sent": sent[0] if sent else None,
            "token": tok[0] if tok else None, "runs": runs}


def all_checks(db_res: dict, market: dict | None, market_err: str, now: datetime, env: dict,
               trading_mode: str) -> list:
    return ([db_res["db"], check_market_data(market, now, market_err), check_pipeline(db_res["last_run"], now),
             check_telegram(db_res["last_sent"], now)]
            + check_tokens(db_res["token"], now)
            + [check_ai(env), check_live(trading_mode), check_risk(db_res["last_run"])])


def recent_errors(runs: list) -> list:
    out = []
    for ev in runs:
        for e in (ev.payload or {}).get("errors") or []:
            out.append((_ist(ev.timestamp), e))
    return out[:8]


def overall(checks: list) -> str:
    sts = [c.status for c in checks]
    return BAD if BAD in sts else WARN if WARN in sts else OK
