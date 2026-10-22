"""NIFTY weekly iron condor — forward PAPER test (no orders are ever placed).

Pre-registered 16 Oct 2026, before the first trade. Rule id: nifty_iron_condor_v1.
Why this trade: option sellers collect an insurance-like premium (the volatility risk
premium); the long wings cap the loss of every trade. A robot keeps the rules exactly.

  Underlying   NIFTY 50 index options (NSE_INDEX|Nifty 50), 1 lot, Rs.1,00,000 capital.
  Entry        a run between 09:30 and 11:30 IST on a trading day, no open condor, and the
               nearest expiry is 4-10 calendar days away (one condor per expiry, at most).
  Strikes      short call = call with delta closest to +0.15 (strike above spot);
               short put  = put with delta closest to -0.15 (strike below spot);
               long wings 200 points further out (nearest listed strike beyond).
  Fills        sell at the bid, buy at the ask (all four legs need a live bid and ask).
  Exits        checked at every run while the market is open:
               cost to close <= 50% of the credit -> TAKE_PROFIT
               cost to close >= 200% of the credit -> STOP_LOSS
               expiry day, run at/after 14:30   -> EXPIRY_CLOSE (at bid/ask)
               expiry passed while still open   -> SETTLED at intrinsic value (NIFTY close)
  Charges      Rs.20 per order, STT 0.1% of sell premium (0.125% of intrinsic on settled
               in-the-money long legs), NSE 0.03503%, SEBI 0.0001%, stamp 0.003% on buys,
               GST 18% on brokerage + exchange + SEBI.
  Safety       cumulative net <= -Rs.15,000 -> new entries stop automatically.
  Verdict      after 30 closed condors: PASS if net > 0, PF >= 1.2 and the annualised
               return on Rs.1,00,000 beats FD 7%.
Storage: audit events OPT_ENTRY / OPT_EXIT (payload JSON); every write is idempotent.
"""
import os
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

RULE_ID = "nifty_iron_condor_v1"
REGISTERED = "2026-10-16"
IST = timezone(timedelta(hours=5, minutes=30))
UNDERLYING = "NSE_INDEX|Nifty 50"
API = "https://api.upstox.com/v2"
ENTRY_START, ENTRY_END = time(9, 30), time(11, 30)
MARKET_OPEN, MARKET_CLOSE = time(9, 15), time(15, 30)
EXPIRY_CLOSE_FROM = time(14, 30)
DTE_MIN, DTE_MAX = 4, 10
TARGET_DELTA = 0.15
WING = 200
TAKE_PROFIT, STOP_MULT = 0.5, 2.0
CAPITAL, FD_RATE = 100000.0, 0.07
MAX_DRAWDOWN_STOP = -15000.0
TARGET_TRADES, PF_MIN = 30, 1.2


# ------------------------------------------------------------------ charges
# NSE options charges (Upstox fee schedule, checked 22 Oct 2026, upstox.com/brokerage-charges):
# brokerage Rs.20/order; STT 0.15% of premium on sell and 0.15% on exercised ITM (from 1 Apr 2026;
# 0.1% / 0.125% before); NSE transaction 0.03553% of premium (from 1 Mar 2026; 0.03503% before);
# SEBI Rs.10/crore; stamp 0.003% on buy; GST 18% on brokerage + transaction + SEBI.
# Owner decision A (22 Oct 2026): condors OPENED from REAL_COSTS_FROM use the 2026 rates; older
# condors keep the rates they were opened with (never re-priced). IPFT (≈Rs.0.50/lakh) is ignored.
RATES_OLD = {"stt_sell": 0.001, "stt_exercise": 0.00125, "exchange": 0.0003503}
RATES_2026 = {"stt_sell": 0.0015, "stt_exercise": 0.0015, "exchange": 0.0003553}


def rates_for(entry_day) -> dict:
    from backtest.backtest_engine import REAL_COSTS_FROM
    return RATES_2026 if entry_day is not None and entry_day >= REAL_COSTS_FROM else RATES_OLD


def leg_charges(premium_value: float, is_sell: bool, entry_day=None) -> float:
    r = rates_for(entry_day)
    brokerage = 20.0
    exchange = premium_value * r["exchange"]
    sebi = premium_value * 0.000001
    stt = premium_value * r["stt_sell"] if is_sell else 0.0
    stamp = 0.0 if is_sell else premium_value * 0.00003
    return brokerage + exchange + sebi + stt + stamp + (brokerage + exchange + sebi) * 0.18


# ------------------------------------------------------------------ Upstox (read-only)
class UpstoxData:
    def __init__(self, token: str | None = None):
        self.token = token if token is not None else os.getenv("UPSTOX_ANALYTICS_TOKEN", "").strip()

    def _get(self, path: str, params: dict) -> dict:
        """Uses `requests` (same as the working sandbox broker): Upstox's Cloudflare
        rejects Python's default urllib client with error 1010."""
        import requests
        if not self.token:
            raise RuntimeError("UPSTOX_ANALYTICS_TOKEN secret is not set")
        resp = requests.get(f"{API}{path}", params=params, timeout=30,
                            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"})
        if resp.status_code != 200:
            raise RuntimeError(f"Upstox {path} HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        if body.get("status") != "success":
            raise RuntimeError(f"Upstox {path}: {str(body)[:200]}")
        return body

    def contracts(self) -> list:
        return self._get("/option/contract", {"instrument_key": UNDERLYING})["data"]

    def chain(self, expiry: date) -> list:
        return self._get("/option/chain", {"instrument_key": UNDERLYING, "expiry_date": str(expiry)})["data"]


# ------------------------------------------------------------------ pure logic
def expiries_and_lot(contracts: list) -> tuple[list, dict]:
    exps, lots = set(), {}
    for c in contracts:
        try:
            d = date.fromisoformat(str(c["expiry"])[:10])
        except Exception:
            continue
        exps.add(d)
        if c.get("lot_size"):
            lots[d] = int(c["lot_size"])
    return sorted(exps), lots


def pick_expiry(expiries: list, today: date):
    future = [e for e in expiries if e >= today]
    if not future:
        return None
    e = future[0]
    return e if DTE_MIN <= (e - today).days <= DTE_MAX else None


def _md(row: dict, side: str) -> dict:
    opt = row.get("call_options" if side == "CE" else "put_options") or {}
    md, gr = opt.get("market_data") or {}, opt.get("option_greeks") or {}
    return {"key": opt.get("instrument_key"), "bid": float(md.get("bid_price") or 0),
            "ask": float(md.get("ask_price") or 0), "ltp": float(md.get("ltp") or 0),
            "delta": gr.get("delta")}


def quotes(chain: list) -> tuple[float, dict]:
    """(spot, {(strike, 'CE'/'PE'): quote})"""
    spot, q = None, {}
    for row in chain:
        k = float(row["strike_price"])
        spot = spot or row.get("underlying_spot_price")
        for side in ("CE", "PE"):
            q[(k, side)] = _md(row, side)
    return float(spot) if spot else None, q


def choose_condor(chain: list):
    """Returns (legs, note). legs = list of dicts (type, strike, side, key); side -1 sell, +1 buy."""
    spot, q = quotes(chain)
    if not spot:
        return None, "no spot price in option chain"
    strikes = sorted({k for k, _ in q})
    calls = [(abs(float(q[(k, "CE")]["delta"]) - TARGET_DELTA), k) for k in strikes
             if k > spot and q[(k, "CE")]["delta"] not in (None, 0)]
    puts = [(abs(abs(float(q[(k, "PE")]["delta"])) - TARGET_DELTA), k) for k in strikes
            if k < spot and q[(k, "PE")]["delta"] not in (None, 0)]
    if not calls or not puts:
        return None, "deltas missing in option chain"
    sc, sp = min(calls)[1], min(puts)[1]
    lc = next((k for k in strikes if k >= sc + WING), None)
    lp = next((k for k in reversed(strikes) if k <= sp - WING), None)
    if lc is None or lp is None:
        return None, "wing strikes not listed"
    legs = [{"type": "CE", "strike": sc, "side": -1}, {"type": "PE", "strike": sp, "side": -1},
            {"type": "CE", "strike": lc, "side": 1}, {"type": "PE", "strike": lp, "side": 1}]
    for leg in legs:
        leg["key"] = q[(leg["strike"], leg["type"])]["key"]
    return legs, f"spot {spot}"


def price_legs(legs: list, chain: list, opening: bool):
    """Fill prices per leg: opening sells at bid / buys at ask; closing reverses.
    Returns list of prices or None if any needed quote is missing."""
    _, q = quotes(chain)
    out = []
    for leg in legs:
        m = q.get((float(leg["strike"]), leg["type"]))
        if not m:
            return None
        selling_now = (leg["side"] < 0) == opening
        px = m["bid"] if selling_now else m["ask"]
        if px <= 0 or m["ask"] < m["bid"]:
            return None
        out.append(px)
    return out


def max_spread_pct(legs: list, chain: list):
    """Widest bid-ask spread among the legs, in % of the mid price. Recorded for information
    (audit 22 Oct 2026); it does NOT block entries — that would change the registered test."""
    _, q = quotes(chain)
    worst = None
    for leg in legs:
        m = q.get((float(leg["strike"]), leg["type"])) or {}
        bid, ask = m.get("bid") or 0, m.get("ask") or 0
        if bid > 0 and ask >= bid:
            pct = (ask - bid) / ((ask + bid) / 2) * 100
            worst = pct if worst is None else max(worst, pct)
    return round(worst, 1) if worst is not None else None


def net_premium(legs: list, prices: list, opening: bool) -> float:
    """Per unit, shorts minus longs: opening -> credit received; closing -> debit paid
    (buy back the shorts at the ask, sell the wings at the bid)."""
    return round(sum(-leg["side"] * p for leg, p in zip(legs, prices)), 2)


def trade_charges(legs: list, prices: list, lot: int, opening: bool, entry_day=None) -> float:
    total = 0.0
    for leg, p in zip(legs, prices):
        selling_now = (leg["side"] < 0) == opening
        total += leg_charges(p * lot, selling_now, entry_day)
    return total


def intrinsic(leg: dict, spot: float) -> float:
    k = float(leg["strike"])
    return max(spot - k, 0.0) if leg["type"] == "CE" else max(k - spot, 0.0)


def settlement(legs: list, spot: float, lot: int, entry_day=None) -> tuple[float, float]:
    """(debit per unit, charges) when held to expiry: shorts pay intrinsic, longs receive it
    (STT on the exercised long legs)."""
    debit = sum(-leg["side"] * intrinsic(leg, spot) for leg in legs)
    rate = rates_for(entry_day)["stt_exercise"]
    charges = sum(intrinsic(leg, spot) * lot * rate for leg in legs if leg["side"] > 0)
    return round(debit, 2), charges


def diagnose(entry: dict, exit_: dict) -> dict:
    """Why a closed condor made or lost money: per leg, the entry and exit price and the rupee effect
    (lot-scaled; shorts lose when the price rises, longs gain). Information only."""
    legs, lot = entry.get("legs") or [], int(entry.get("lot") or 0)
    prices = exit_.get("exit_prices")
    rows = []
    for i, leg in enumerate(legs):
        px = prices[i] if prices and i < len(prices) else None
        e = leg.get("entry")
        # a short leg (side -1) gains (entry - exit) per unit; a long leg (side +1) gains (exit - entry)
        effect = None if px is None or e is None else round((px - e) * leg["side"] * lot, 2)
        rows.append({"leg": f'{"SELL" if leg["side"] < 0 else "BUY"} {leg["strike"]:.0f}{leg["type"]}',
                     "entry": e, "exit": px, "effect": effect})
    worst = min((r for r in rows if r["effect"] is not None), key=lambda r: r["effect"], default=None)
    t0, t1 = str(entry.get("time", ""))[:16], str(exit_.get("time", ""))[:16]
    return {"legs": rows, "credit": entry.get("credit"), "debit": exit_.get("debit"),
            "same_day": t0[:10] == t1[:10], "opened": t0.replace("T", " "), "closed": t1.replace("T", " "),
            "worst_leg": worst["leg"] if worst else None, "reason": exit_.get("reason"),
            "charges": round((entry.get("entry_charges") or 0) + (exit_.get("exit_charges") or 0), 2)}


def exit_decision(credit: float, debit: float, now: datetime, expiry: date):
    if debit <= credit * TAKE_PROFIT:
        return "TAKE_PROFIT"
    if debit >= credit * STOP_MULT:
        return "STOP_LOSS"
    if now.date() == expiry and now.time() >= EXPIRY_CLOSE_FROM:
        return "EXPIRY_CLOSE"
    return None


# The annualised figure is shown only after this many closed condors: from one or two results a
# yearly rate is meaningless (display only; the verdict at 30 condors is unchanged).
ANNUAL_MIN_CLOSED = 10


def stats(exits: list, first_entry: date | None, today: date) -> dict:
    nets = [e["net_pnl"] for e in exits]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    net = round(sum(nets), 2)
    days = max((today - first_entry).days, 1) if first_entry else None
    annual = round(net / CAPITAL * 365 / days * 100, 2) if days else None
    pf = round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else (99.0 if wins else None)
    done = len(nets) >= TARGET_TRADES
    verdict = None
    if done:
        verdict = "PASS" if net > 0 and (pf or 0) >= PF_MIN and (annual or 0) > FD_RATE * 100 else "FAIL"
    return {"closed": len(nets), "net": net, "pf": pf, "annual_pct": annual,
            "worst": min(nets) if nets else None, "verdict": verdict,
            "paused": net <= MAX_DRAWDOWN_STOP}


# ------------------------------------------------------------------ the run
@dataclass
class OptReport:
    lines: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    activity: bool = False


def _now() -> datetime:
    return datetime.now(IST)


def _events(db, kind: str) -> list:
    return [e.payload for e in db.get_audit_events(kind, limit=500)
            if (e.payload or {}).get("rule") == RULE_ID]


def _save(db, kind: str, payload: dict) -> None:
    from database.models import AuditEvent
    db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type=kind,
                                   symbol="NIFTY", payload={"rule": RULE_ID, **payload}))


def _nifty_close_on(d: date):
    from backtest.backtest_engine import _nifty_series
    s = _nifty_series(datetime.combine(d - timedelta(days=7), time(0)), datetime.combine(d + timedelta(days=1), time(0)))
    vals = [c for dd, c in s if dd == d]
    return vals[0] if vals else None


def _is_trading_day(d: date) -> bool:
    from backtest.backtest_engine import _nifty_series
    s = _nifty_series(datetime.combine(d - timedelta(days=7), time(0)), datetime.combine(d + timedelta(days=1), time(0)))
    return bool(s) and s[-1][0] == d


def run(db, data: UpstoxData | None = None, now: datetime | None = None, allow_entries: bool = True,
        nifty_close_on=_nifty_close_on, is_trading_day=_is_trading_day) -> OptReport:
    now = now or _now()
    rep = OptReport()
    data = data or UpstoxData()
    entries = _events(db, "OPT_ENTRY")
    exits = _events(db, "OPT_EXIT")
    closed_ids = {e["id"] for e in exits}
    open_pos = [e for e in entries if e["id"] not in closed_ids]
    market_open = MARKET_OPEN <= now.time() <= MARKET_CLOSE and now.weekday() < 5

    # ---- exits
    for pos in open_pos:
        expiry = date.fromisoformat(pos["expiry"])
        legs, lot, credit = pos["legs"], pos["lot"], pos["credit"]
        opened = date.fromisoformat(pos["time"][:10])
        try:
            if now.date() > expiry or (now.date() == expiry and now.time() > MARKET_CLOSE):
                spot = nifty_close_on(expiry)
                if spot is None:
                    rep.errors.append(f"condor {pos['id']}: NIFTY close for {expiry} not available yet")
                    continue
                debit, ch = settlement(legs, spot, lot, opened)
                reason, prices = "SETTLED", None
            elif market_open:
                chain = data.chain(expiry)
                prices = price_legs(legs, chain, opening=False)
                if prices is None:
                    rep.errors.append(f"condor {pos['id']}: quotes missing, exit check skipped")
                    continue
                debit = net_premium(legs, prices, opening=False)
                reason = exit_decision(credit, debit, now, expiry)
                if not reason:
                    continue
                ch = trade_charges(legs, prices, lot, opening=False, entry_day=opened)
            else:
                continue
            pnl = round((credit - debit) * lot - pos["entry_charges"] - ch, 2)
            _save(db, "OPT_EXIT", {"id": pos["id"], "time": now.isoformat(), "reason": reason,
                                   "debit": debit, "exit_prices": prices, "exit_charges": round(ch, 2),
                                   "net_pnl": pnl})
            exits.append({"id": pos["id"], "net_pnl": pnl})
            closed_ids.add(pos["id"])
            rep.activity = True
            rep.lines.append(f"🔴 Condor {pos['id']} {reason}: credit {credit} → close {debit} | net Rs.{pnl}")
        except Exception as e:
            rep.errors.append(f"condor {pos['id']} exit: {e}")

    # ---- entries
    first = min((date.fromisoformat(e["time"][:10]) for e in entries), default=None)
    st = stats(exits, first, now.date())
    still_open = [e for e in entries if e["id"] not in closed_ids]
    if (allow_entries and not st["paused"] and not still_open and now.weekday() < 5
            and ENTRY_START <= now.time() < ENTRY_END):
        try:
            if not is_trading_day(now.date()):
                raise _Skip("market closed today")
            expiries, lots = expiries_and_lot(data.contracts())
            expiry = pick_expiry(expiries, now.date())
            if expiry is None:
                raise _Skip("no expiry 4-10 days away today")
            cid = f"IC-{expiry}"
            if any(e["id"] == cid for e in entries):
                raise _Skip(f"condor for {expiry} already traded")
            lot = lots.get(expiry)
            if not lot:
                raise RuntimeError(f"lot size unknown for {expiry}")
            chain = data.chain(expiry)
            legs, note = choose_condor(chain)
            if legs is None:
                raise RuntimeError(note)
            prices = price_legs(legs, chain, opening=True)
            if prices is None:
                raise _Skip("bid/ask missing on a leg — retry next run")
            credit = net_premium(legs, prices, opening=True)
            if credit <= 0:
                raise _Skip(f"credit {credit} not positive")
            ch = round(trade_charges(legs, prices, lot, opening=True, entry_day=now.date()), 2)
            for leg, p in zip(legs, prices):
                leg["entry"] = p
            spread = max_spread_pct(legs, chain)
            _save(db, "OPT_ENTRY", {"id": cid, "time": now.isoformat(), "expiry": str(expiry), "lot": lot,
                                    "legs": legs, "credit": credit, "entry_charges": ch, "note": note,
                                    "max_spread_pct": spread})
            rep.activity = True
            width = WING
            rep.lines.append(
                f"🟢 Condor {cid}: sell {legs[1]['strike']:.0f}PE/{legs[0]['strike']:.0f}CE, "
                f"buy {legs[3]['strike']:.0f}PE/{legs[2]['strike']:.0f}CE | credit {credit} x {lot} = "
                f"Rs.{credit * lot:,.0f} | max loss ≈ Rs.{(width - credit) * lot:,.0f} | {note}"
                + (f" | widest bid-ask {spread}%" if spread is not None else ""))
        except _Skip as s:
            rep.lines.append(f"ℹ️ Options: {s}")
        except Exception as e:
            rep.errors.append(f"options entry: {e}")
    elif st["paused"] and allow_entries:
        rep.lines.append(f"⛔ Options paused: cumulative net Rs.{st['net']} ≤ Rs.{MAX_DRAWDOWN_STOP:,.0f}")

    st = stats(exits, first, now.date())
    rep.lines.append(f"📊 Options condor v1: closed {st['closed']}/{TARGET_TRADES}, open "
                     f"{len([e for e in entries if e['id'] not in closed_ids])}, net Rs.{st['net']}"
                     + (f", PF {st['pf']}" if st["pf"] else "")
                     + (f", annualised {st['annual_pct']}%" if st["annual_pct"] is not None
                        and st["closed"] >= ANNUAL_MIN_CLOSED else "")
                     + (f" | VERDICT {st['verdict']}" if st["verdict"] else ""))
    return rep


class _Skip(Exception):
    pass
