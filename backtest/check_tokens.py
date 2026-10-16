"""Automatic expiry warning for the Upstox tokens kept in GitHub secrets.

Upstox tokens are JWTs: the expiry ("exp") can be read from the token itself without
any network call. Once per day (evening run, or any manual run) a Telegram warning is
sent when a token expires within WARN_DAYS or has already expired. Never prints tokens.
"""
import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

IST = timezone(timedelta(hours=5, minutes=30))
WARN_DAYS = 5
TOKENS = {
    "UPSTOX_SANDBOX_TOKEN": ("Upstox sandbox token (stock orders mirror)",
                             "Upstox Developer Apps → Sandbox app → Generate token → GitHub Settings → "
                             "Secrets → Actions → UPSTOX_SANDBOX_TOKEN → Update"),
    "UPSTOX_ANALYTICS_TOKEN": ("Upstox analytics token (options data)",
                               "Upstox Developer Apps → Analytics → Generate token → GitHub Settings → "
                               "Secrets → Actions → UPSTOX_ANALYTICS_TOKEN → Update"),
}


def jwt_expiry(token: str):
    """UTC expiry datetime from a JWT, or None if it can't be read."""
    try:
        part = token.strip().split(".")[1]
        part += "=" * (-len(part) % 4)
        exp = json.loads(base64.urlsafe_b64decode(part)).get("exp")
        return datetime.fromtimestamp(int(exp), tz=timezone.utc) if exp else None
    except Exception:
        return None


def warnings(env: dict, now: datetime) -> list:
    out = []
    for name, (label, how) in TOKENS.items():
        tok = (env.get(name) or "").strip()
        if not tok:
            continue
        exp = jwt_expiry(tok)
        if exp is None:
            continue
        days = (exp - now).total_seconds() / 86400
        when = exp.astimezone(IST).strftime("%d %b %Y %H:%M IST")
        if days <= 0:
            out.append(f"❌ {label} EXPIRED on {when}.\nRenew: {how}")
        elif days <= WARN_DAYS:
            out.append(f"⏰ {label} expires on {when} ({days:.1f} days).\nRenew: {how}")
    return out


def status(env: dict, now: datetime) -> list:
    """One line per configured token (for manual runs): expiry date or 'not readable'."""
    out = []
    for name, (label, _) in TOKENS.items():
        tok = (env.get(name) or "").strip()
        if not tok:
            out.append(f"• {label}: not set")
            continue
        exp = jwt_expiry(tok)
        out.append(f"• {label}: " + (f"valid until {exp.astimezone(IST):%d %b %Y} "
                                      f"({(exp - now).days} days)" if exp else "expiry not readable"))
    return out


def main() -> int:
    now = datetime.now(timezone.utc)
    msgs = warnings(os.environ, now)
    manual = os.getenv("RUN_SOURCE", "").strip().lower() == "manual"
    if manual:
        msgs = msgs + ["Token status:\n" + "\n".join(status(os.environ, now))]
    evening = now.astimezone(IST).hour >= 16
    print(f"{len(msgs)} token warning(s)")
    if not msgs or not (manual or evening):
        return 0
    from backtest.run_rule_paper import _first_time_today, send_telegram
    text = "🔑 Garud token check\n" + "\n\n".join(msgs)
    try:
        from config.settings import load_settings
        from database.db import Database
        db = Database(load_settings())
        db.connect()
        first = _first_time_today(db, "tokens", now.astimezone(IST), text)
    except Exception:
        first = True
    if manual or first:
        send_telegram(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
