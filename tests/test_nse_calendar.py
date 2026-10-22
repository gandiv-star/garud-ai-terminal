"""NSE holiday calendar and the Health data-freshness check."""
from datetime import date, datetime, timedelta, timezone

import garud_health as gh
from backtest import nse_calendar as nc

IST = timezone(timedelta(hours=5, minutes=30))


def test_sessions_and_holidays():
    assert not nc.is_session(date(2026, 10, 20))          # Dussehra
    assert not nc.is_session(date(2026, 10, 24))          # Saturday
    assert nc.is_session(date(2026, 10, 21))
    assert nc.previous_session(date(2026, 10, 20)) == date(2026, 10, 19)
    assert nc.previous_session(date(2026, 11, 10)) == date(2026, 11, 9)   # Diwali Balipratipada
    assert nc.sessions_between(date(2026, 10, 16), date(2026, 10, 21)) == 2   # Mon 19, (Tue 20 holiday), Wed 21
    assert nc.known_year(2026) and not nc.known_year(2027)
    assert all(d.weekday() < 5 for d in nc.HOLIDAYS[2026])


def test_health_not_stale_on_a_holiday():
    on_holiday = datetime(2026, 10, 20, 16, 0, tzinfo=IST)
    assert gh.last_session(on_holiday) == date(2026, 10, 19)
    c = gh.check_market_data({"date": "2026-10-19"}, on_holiday)
    assert c.status == gh.OK
    next_morning = datetime(2026, 10, 21, 9, 0, tzinfo=IST)      # before the open
    assert gh.check_market_data({"date": "2026-10-19"}, next_morning).status == gh.OK
    later = datetime(2026, 10, 23, 16, 0, tzinfo=IST)
    assert gh.check_market_data({"date": "2026-10-19"}, later).status == gh.BAD
