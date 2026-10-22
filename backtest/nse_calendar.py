"""NSE equity trading calendar (weekends + exchange holidays).

Used by the 🩺 Health screen so a holiday is not reported as "data stuck". Trading decisions do
not depend on this list: paper rules enter only when today's bar exists, and momentum refuses
prices older than 6 days.
2026 list: NSE equity segment holidays as published by NSE (cross-checked 22 Oct 2026 with
cleartax.in and upstox.com). ADD NEXT YEAR'S LIST when NSE publishes it (usually December);
for a year that is missing, only weekends are known (the old behaviour).
"""
from datetime import date, timedelta

HOLIDAYS = {
    2026: (date(2026, 1, 15), date(2026, 1, 26), date(2026, 3, 3), date(2026, 3, 26), date(2026, 3, 31),
           date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 5, 28), date(2026, 6, 26),
           date(2026, 9, 14), date(2026, 10, 2), date(2026, 10, 20), date(2026, 11, 10), date(2026, 11, 24),
           date(2026, 12, 25)),
}
_ALL = frozenset(d for days in HOLIDAYS.values() for d in days)


def known_year(year: int) -> bool:
    return year in HOLIDAYS


def is_session(d: date) -> bool:
    return d.weekday() < 5 and d not in _ALL


def previous_session(d: date) -> date:
    """The latest session on or before d."""
    while not is_session(d):
        d -= timedelta(days=1)
    return d


def sessions_between(a: date, b: date) -> int:
    """Sessions after a, up to and including b."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        n += is_session(d)
    return n
