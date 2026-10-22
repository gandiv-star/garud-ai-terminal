"""Live-readiness checklist (#69, #140) — what must be true before ANY real-money order.

Computed from what Garud can see (paper verdicts, the live switches and limits the automatic run
reported, the compliance review date). Items Garud cannot see from code (static IP, Upstox algo
onboarding, Algo-ID) are listed as MANUAL. Information only: it never switches anything on.
"""
from datetime import date

COMPLIANCE_REVIEWED = date(2026, 9, 15)     # docs/COMPLIANCE.md "Last researched: September 2026"
REVIEW_MAX_DAYS = 60
OK, TODO, MANUAL = "OK", "TODO", "MANUAL"


def checklist(rule_statuses: dict, live: dict | None, momentum_months: int, today: date) -> list:
    """rule_statuses: {rule title: checkpoint status text}; live: PIPELINE_RUN 'live' block;
    momentum_months: completed monthly rebalances of the momentum paper portfolios.
    Returns [(item, status, detail)]."""
    live = live or {}
    passed = [t for t, s in rule_statuses.items() if "VERDICT: PASS" in (s or "")]
    out = [
        ("A strategy PASSED its paper test", OK if passed else TODO,
         ", ".join(passed) if passed else "no swing rule has 30 trades yet; momentum decision Feb 2027 "
                                          f"({momentum_months}/3 months of paper)"),
        ("Live switches are OFF until the owner decides", OK if not live.get("orders_allowed") else TODO,
         "TRADING_MODE / LIVE_ORDERS_ENABLED not set" if not live.get("orders_allowed") else "live orders are ALLOWED"),
        ("Live limit variables valid (fail-closed)", OK if not live.get("problems") else TODO,
         "; ".join(live.get("problems") or []) or "all unset or valid"),
        ("Execution safety (order states, partial fills, tick size, cash, reconciliation)", OK,
         "built and tested with a fake broker (tests/test_execution_safety.py); never exercised with real money"),
        ("Order rate far below 10 orders/second", OK, "max 5 open positions, one order at a time"),
        ("Compliance checklist re-checked recently",
         OK if (today - COMPLIANCE_REVIEWED).days <= REVIEW_MAX_DAYS else TODO,
         f"last reviewed {COMPLIANCE_REVIEWED:%d %b %Y} (docs/COMPLIANCE.md)"),
        ("Static IP server registered with Upstox", MANUAL, "required for live order APIs; not set up"),
        ("Upstox retail-algo onboarding + Algo-ID on orders", MANUAL, "confirm with Upstox before the first order"),
        ("Daily Upstox LIVE token process", MANUAL, "BROKER_ACCESS_TOKEN expires daily; not set up"),
        ("Weekly restore drill OK", MANUAL, "check Sunday's Telegram: 'Full restore drill … integrity OK'"),
    ]
    return out


def ready(items: list) -> bool:
    return all(s == OK for _, s, _ in items)
