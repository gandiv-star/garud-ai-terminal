"""Token expiry warnings never print the token itself."""
import base64
import json
from datetime import datetime, timedelta, timezone

import backtest.check_tokens as ct

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def jwt(exp):
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f"{b({'alg': 'HS256'})}.{b({'sub': 'x', 'exp': int(exp.timestamp())})}.sig"


def test_warns_within_five_days_only():
    env = {"UPSTOX_SANDBOX_TOKEN": jwt(NOW + timedelta(days=3)), "UPSTOX_ANALYTICS_TOKEN": jwt(NOW + timedelta(days=300))}
    w = ct.warnings(env, NOW)
    assert len(w) == 1 and "sandbox" in w[0] and "3.0 days" in w[0]
    assert all(env["UPSTOX_SANDBOX_TOKEN"] not in x for x in w)


def test_expired_and_garbage():
    w = ct.warnings({"UPSTOX_SANDBOX_TOKEN": jwt(NOW - timedelta(hours=1))}, NOW)
    assert "EXPIRED" in w[0]
    assert ct.warnings({"UPSTOX_SANDBOX_TOKEN": "not-a-jwt"}, NOW) == []
    assert ct.warnings({}, NOW) == []
