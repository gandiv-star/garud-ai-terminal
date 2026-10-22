"""Forward PAPER portfolios for the monthly momentum engines (no orders are ever placed).

Started 19-21 Oct 2026 (owner approved): first signal at the 30 Oct 2026 month-end close.
  M2  Momentum 200 + weak-market switch  (backtest/momentum200.py, passed its 15-year check)
  G   NIFTY 50 momentum + weak-market switch (backtest/longterm.py / momentum200.g_weights)
Paper capital: M2 Rs.3,00,000 (20 stocks), G Rs.1,00,000 (10 stocks) — so each slot is about
Rs.15,000 / Rs.10,000. (21 Oct dry run on real prices: with Rs.1,00,000 and 20 slots of Rs.5,000,
whole-share rounding and unaffordable shares left ~42% of M2 in cash — not the tested strategy.) Exactly the backtest's rule: decide on the
month-end close, trade at the NEXT trading day's close, equal weight, 2% no-trade band, real
delivery charges, idle cash earns the liquid-fund rate (6.5%). One difference, on purpose:
real trades are in WHOLE shares (the backtest used fractions), so a stock whose price is above
its slot cannot be bought in full. Rounding rule: first whole shares that fit the slot, then
leftover cash buys one more share wherever that brings a stock CLOSER to its target (so a share
priced up to 2x the slot can still be bought; above that it stays in cash).

State lives in the database as events, never edited:
  MOM_PAPER  one per portfolio per rebalance: holdings, cash, trades, value after trading
  MOM_NAV    one per portfolio per trading day: value at the close (+ NIFTY close for comparison)
A missed run catches up: a month-end whose next trading day has passed is filled at that day's
close from the price history, exactly as if the run had happened on time.
"""
import math
from datetime import date, datetime, time, timedelta, timezone

from backtest import longterm as lt
from backtest.backtest_engine import ChargeModel

START_SIGNAL = date(2026, 10, 30)
CAPITALS = {"M2": 300000.0, "G": 100000.0}
CAPITAL = 100000.0          # default for any other portfolio id
LIQUID_RATE = lt.LIQUID_RATE
BAND = lt.NO_TRADE_BAND
EV_REBAL, EV_NAV = "MOM_PAPER", "MOM_NAV"
PORTFOLIOS = {"M2": "Momentum 200 + weak-market switch", "G": "NIFTY 50 momentum + weak-market switch"}
IST = timezone(timedelta(hours=5, minutes=30))
CLOSE_DONE = time(15, 35)


def capital_of(pid: str) -> float:
    return CAPITALS.get(pid, CAPITAL)


def initial_state(pid: str) -> dict:
    cap = capital_of(pid)
    return {"portfolio": pid, "cash": cap, "units": {}, "last_px": {}, "held": [], "month": None,
            "as_of": None, "value": cap, "capital": cap}


def latest_state(db, pid: str) -> dict:
    for ev in db.get_audit_events(EV_REBAL, limit=200):
        p = ev.payload or {}
        if p.get("portfolio") == pid:
            return p
    return initial_state(pid)


def completed_dates(dates: list, now: datetime) -> int:
    """Index of the last session whose close is final at `now` (today's bar only after 15:35 IST)."""
    last = len(dates) - 1
    if last >= 0 and dates[last] == now.date() and now.time() < CLOSE_DONE:
        last -= 1
    return last


def due_month_ends(dates: list, last_done: int, month_done: str | None) -> list:
    """Month-end session indices m (signal) whose next session m+1 (fill) is complete and
    whose month has not been processed yet, oldest first."""
    out = []
    for m in range(0, last_done):
        if dates[m].month != dates[m + 1].month and dates[m] >= START_SIGNAL:
            key = f"{dates[m]:%Y-%m}"
            if month_done is None or key > month_done:
                out.append(m)
    return out


def accrue(cash: float, from_day, to_day) -> float:
    if not from_day or to_day <= from_day:
        return cash
    return cash * (1 + LIQUID_RATE) ** ((to_day - from_day).days / 365)


def rebalance(state: dict, prices: dict, want: dict, fill_day: date, allow_buys: bool = True,
              cm: ChargeModel | None = None) -> dict:
    """Moves the account to the target weights at the fill-day closes (whole shares).
    prices: {symbol: close on the fill day}. Returns the new state (input is not modified)."""
    cm = cm or ChargeModel()
    as_of = date.fromisoformat(state["as_of"]) if state.get("as_of") else None
    cash = accrue(float(state["cash"]), as_of, fill_day)
    units = {s: int(q) for s, q in (state.get("units") or {}).items() if int(q) > 0}
    last_px = dict(state.get("last_px") or {})
    last_px.update({s: p for s, p in prices.items() if p})
    px = lambda s: prices.get(s) or last_px.get(s)  # noqa: E731
    value = cash + sum(q * px(s) for s, q in units.items() if px(s))
    want = {s: w for s, w in want.items() if w > 0 and prices.get(s)}
    trades = []
    for s in sorted(set(units) | set(want)):
        p = prices.get(s)
        if not p or s not in units:
            continue
        cur = units[s] * p
        diff = want.get(s, 0) * value - cur
        if diff < 0 and (abs(diff) >= BAND * value or s not in want):
            qty = units[s] if s not in want else min(units[s], math.ceil(-diff / p))
            if qty <= 0:
                continue
            gross = qty * p
            cash += gross - cm.sell_charges(gross)
            units[s] -= qty
            if units[s] <= 0:
                units.pop(s)
            trades.append({"side": "SELL", "symbol": s, "qty": qty, "price": round(p, 2)})
    if allow_buys:
        buys = {}
        for s, w in want.items():
            p = prices[s]
            diff = w * value - units.get(s, 0) * p
            if diff > 0 and (diff >= BAND * value or s not in units):
                buys[s] = diff
        need = sum(buys.values()) * 1.002
        scale = min(1.0, cash / need) if need > 0 else 0.0
        bought = {}

        def cost(sym, q):          # one order per symbol: price + charges (flat brokerage counted once)
            return q * prices[sym] + cm.buy_charges(q * prices[sym]) if q > 0 else 0.0
        for s in sorted(buys):
            p = prices[s]
            qty = int(buys[s] * scale // p)
            while qty > 0 and cost(s, qty) > cash:
                qty -= 1
            if qty > 0:
                cash -= cost(s, qty)
                bought[s] = qty
        # leftover cash: one more share where it brings the stock closer to its target weight
        for _ in range(500):
            best, best_gap = None, 0.0
            for s in buys:
                p = prices[s]
                b = bought.get(s, 0)
                gap = want[s] * value - (units.get(s, 0) + b) * p
                if gap > p / 2 and cost(s, b + 1) - cost(s, b) + p * 0.003 <= cash and gap > best_gap:
                    best, best_gap = s, gap
            if best is None:
                break
            b = bought.get(best, 0)
            cash -= cost(best, b + 1) - cost(best, b)
            bought[best] = b + 1
        for s in sorted(bought):
            units[s] = units.get(s, 0) + bought[s]
            trades.append({"side": "BUY", "symbol": s, "qty": bought[s], "price": round(prices[s], 2)})
    value = cash + sum(q * px(s) for s, q in units.items() if px(s))
    return {**state, "cash": round(cash, 2), "units": units,
            "last_px": {s: round(last_px[s], 2) for s in units if s in last_px},
            "as_of": str(fill_day), "value": round(value, 2), "trades": trades}


def mark(state: dict, prices: dict, day: date) -> float:
    """Value at the close of `day` (no trading)."""
    as_of = date.fromisoformat(state["as_of"]) if state.get("as_of") else None
    cash = accrue(float(state["cash"]), as_of, day)
    last = state.get("last_px") or {}
    return round(cash + sum(q * (prices.get(s) or last.get(s) or 0) for s, q in (state.get("units") or {}).items()), 2)


def save(db, event_type: str, payload: dict) -> None:
    from database.models import AuditEvent
    db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type=event_type, symbol=None,
                                   payload=payload))


def nav_saved(db, pid: str, day: date) -> bool:
    return any((ev.payload or {}).get("portfolio") == pid and (ev.payload or {}).get("date") == str(day)
               for ev in db.get_audit_events(EV_NAV, limit=60))


def first_nifty(db) -> float | None:
    navs = [ev.payload or {} for ev in db.get_audit_events(EV_NAV, limit=5000)]
    navs = [p for p in navs if p.get("nifty")]
    return min(navs, key=lambda p: p["date"])["nifty"] if navs else None
