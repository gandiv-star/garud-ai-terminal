"""Engine 2 — Swing 2.0: buy short pullbacks in the market's strongest stocks (15-year portfolio test).

Pre-registered 21 Oct 2026, before running. One shared Rs.1,00,000 account, 15 years ending
rule_report.BENCHMARK_END, gap-aware fills + slippage (FillModel v2), real delivery charges,
idle cash at the liquid-fund rate (6.5%).

Leaders (refreshed every month-end): 12-1 momentum (return from 252 to 21 sessions ago).
  S50  : point-in-time NIFTY 50 list -> top 15 leaders            (no survivorship bias)
  S200 : today's NIFTY 200 + every NIFTY 50 member since 2010, the 150 most liquid by 6-month
         traded value -> top 30 leaders                           (biased: optimistic)
Entry signal at a close: the stock is a current leader, its close is above its 200-day average
  (uptrend intact) and at least 5% below its highest close of the last 10 sessions (a pullback).
  Several signals -> strongest leader first. Buy at the next open.
Exit: close above its 5-day average (the bounce) -> sell at that close; or 10 sessions held;
  or stop 2 x ATR(14) below entry (gap-down fills at the open). Max 5 positions, 20% of equity each.
Weak market (NIFTY regime not MODERATE_BULL/WEAK_BULL) — the owner asked to test, not assume:
  W-off  : buy as usual in a weak market
  W-half : buy in a weak market at half size (10% of equity)
  W-stop : no new buys in a weak market (open positions follow their own exits)
PASS = 15-year CAGR > 7% AND max drawdown <= 25% (same bar as Phase 2).
Choice rule (fixed now): the version for paper trading is the PASSING S50 row with the highest
CAGR / max-drawdown; S200 rows are information only (bias). PASS = paper candidate, not profit.
"""
from bisect import bisect_right
from datetime import date, timedelta

from backtest import longterm as lt
from backtest import portfolio15 as pf
from backtest.backtest_engine import ChargeModel, FillModel, _regime_at

VERSION = 1
CAPITAL = 100000.0
MAX_OPEN, SLOT_PCT = 5, 20.0
PULLBACK_PCT, HIGH_DAYS, TREND_DAYS, EXIT_SMA, MAX_HOLD = 5.0, 10, 200, 5, 10
STOP_ATR = 2.0
MOM_LONG, MOM_SKIP = 252, 21
BULL = ("MODERATE_BULL", "WEAK_BULL")
WEAK_MODES = {"W-off": 1.0, "W-half": 0.5, "W-stop": 0.0}   # size multiplier in a weak market
UNIVERSES = {"S50": 15, "S200": 30}                          # leaders kept per universe
LIQUID_TOP = 150


def _atr(bars, n=14):
    if len(bars) < n + 1:
        return None
    trs = [max(b.high - b.low, abs(b.high - a.close), abs(b.low - a.close)) for a, b in zip(bars[-n - 1:-1], bars[-n:])]
    return sum(trs) / n


def momentum(u: pf.Universe, s: str, i: int):
    if i - MOM_LONG < 0:
        return None
    a, age_a = u.last_close(s, i - MOM_LONG)
    b, age_b = u.last_close(s, i - MOM_SKIP)
    if not a or not b or age_a > 5 or age_b > 5 or u.bar(s, i) is None:
        return None
    return b / a - 1


def traded_value(u: pf.Universe, s: str, i: int, n: int = 126) -> float:
    h = u.history(s, i, n)
    return sum(b.close * (b.volume or 0) for b in h) / n if h else 0.0


def leaders(u: pf.Universe, i: int, pool, top: int, liquid_top: int | None = None) -> list:
    pool = [s for s in pool if s in u.bars]
    if liquid_top:
        pool = [s for _, s in sorted(((traded_value(u, s, i), s) for s in pool), reverse=True)[:liquid_top]]
    scored = sorted(((m, s) for s in pool if (m := momentum(u, s, i)) is not None), reverse=True)
    return [s for _, s in scored[:top]]


def entry_signal(u: pf.Universe, s: str, i: int):
    """ATR when the stock shows a pullback in an intact uptrend at session i, else None."""
    h = u.history(s, i, TREND_DAYS)
    if len(h) < TREND_DAYS:
        return None
    close = h[-1].close
    sma200 = sum(b.close for b in h) / TREND_DAYS
    high10 = max(b.close for b in h[-HIGH_DAYS:])
    if close > sma200 and close <= high10 * (1 - PULLBACK_PCT / 100):
        return _atr(h)
    return None


def simulate(u: pf.Universe, start_i: int, pool_fn, top: int, weak_mult: float, liquid_top: int | None = None,
             fill: FillModel | None = None, cm: ChargeModel | None = None) -> dict:
    fill, cm = fill or FillModel(), cm or ChargeModel()
    cash, pos, pending, lead, trades, curve = CAPITAL, {}, [], [], [], []
    invested = 0.0

    def equity(i):
        v = cash
        for s, p in pos.items():
            px, _ = u.last_close(s, i)
            v += p["qty"] * (px or p["entry"])
        return v

    def close_pos(s, price, i, reason):
        nonlocal cash
        p = pos.pop(s)
        gross = p["qty"] * price
        cash += gross - cm.sell_charges(gross)
        trades.append({"symbol": s, "entry_date": str(u.dates[p["entry_i"]]), "exit_date": str(u.dates[i]),
                       "net": round((price - p["entry"]) * p["qty"] - p["bc"] - cm.sell_charges(gross), 2),
                       "reason": reason, "weak": p["weak"]})

    for i in range(start_i, len(u.dates)):
        if i > start_i:
            cash *= (1 + lt.LIQUID_RATE) ** ((u.dates[i] - u.dates[i - 1]).days / 365)
        if i == start_i or u.dates[i].month != u.dates[i - 1].month:
            lead = leaders(u, i - 1 if i > 0 else i, pool_fn(u.dates[max(i - 1, 0)]), top, liquid_top)
        # entries at today's open
        if pending:
            eq = equity(i - 1)
            for s, atr, mult, weak in pending:
                if len(pos) >= MAX_OPEN or s in pos:
                    continue
                b = u.bar(s, i)
                if b is None or not atr:
                    continue
                price = fill.entry_price(b.open)
                qty = int(eq * SLOT_PCT / 100 * mult // price)
                while qty > 0 and qty * price + cm.buy_charges(qty * price) > cash:
                    qty -= 1
                if qty <= 0:
                    continue
                bc = cm.buy_charges(qty * price)
                cash -= qty * price + bc
                pos[s] = {"qty": qty, "entry": price, "stop": price - STOP_ATR * atr, "entry_i": i, "held": 0,
                          "bc": bc, "weak": weak}
            pending = []
        # exits on today's bar
        for s in list(pos):
            p, b = pos[s], u.bar(s, i)
            if b is None:
                px, age = u.last_close(s, i)
                if age is not None and age >= pf.STALE_DAYS:
                    close_pos(s, fill.time_exit_price(px), i, "NO_DATA")
                continue
            if i > p["entry_i"]:
                p["held"] += 1
            if b.low <= p["stop"]:
                close_pos(s, fill.stop_exit_price(b.open, p["stop"]), i, "STOP_GAP" if b.open < p["stop"] else "STOP")
                continue
            if p["held"] >= 1:
                h = u.history(s, i, EXIT_SMA)
                if len(h) == EXIT_SMA and b.close > sum(x.close for x in h) / EXIT_SMA:
                    close_pos(s, fill.time_exit_price(b.close), i, "BOUNCE")
                    continue
            if p["held"] >= MAX_HOLD:
                close_pos(s, fill.time_exit_price(b.close), i, "TIME")
        # signals at today's close
        if i + 1 < len(u.dates) and len(pos) < MAX_OPEN:
            weak = _regime_at(u.nifty[: i + 1]).regime.value not in BULL
            mult = weak_mult if weak else 1.0
            if mult > 0:
                sig = []
                for rank, s in enumerate(lead):
                    if s in pos or u.bar(s, i) is None:
                        continue
                    atr = entry_signal(u, s, i)
                    if atr:
                        sig.append((rank, s, atr))
                pending = [(s, atr, mult, weak) for _, s, atr in sorted(sig)[: MAX_OPEN - len(pos)]]
        value = equity(i)
        if value > 0:
            invested += (value - cash) / value
        curve.append((u.dates[i], value))
    return {"curve": curve, "trades": trades, "exposure_pct": round(invested / max(len(curve), 1) * 100, 1)}


def stats(trades: list) -> dict:
    s = pf.trade_stats(trades)
    weak = [t["net"] for t in trades if t["weak"]]
    s["weak_trades"] = len(weak)
    s["weak_net"] = round(sum(weak), 2)
    return s


def run(u: pf.Universe, mkt, eval_start: date, pools: dict) -> dict:
    """pools: {'S50': members_fn(date) -> symbols, 'S200': members_fn}."""
    start_i = max(bisect_right(u.dates, eval_start) - 1, 0)
    start, end = u.dates[start_i], u.dates[-1]
    split = start + timedelta(days=pf.DECADE_DAYS)
    rows = []
    fd = [(d, CAPITAL * (1 + lt.FD_RATE) ** ((d - start).days / 365)) for d in u.dates[start_i:]]
    rows.append({"strategy": "FD 7%", **lt._windows(fd, start, split, end), "yearly": lt.yearly(fd)})
    mi = max(bisect_right(mkt.dates, eval_start) - 1, 0)
    bh, _ = lt.simulate(mkt, mi, lambda i: {lt.ETF: 1.0}, [mi - 1] if mi > 0 else [mi])
    rows.append({"strategy": "NIFTY buy & hold", **lt._windows(bh, start, split, end), "yearly": lt.yearly(bh)})
    for uni, top in UNIVERSES.items():
        if uni not in pools:
            continue
        for mode, mult in WEAK_MODES.items():
            sim = simulate(u, start_i, pools[uni], top, mult, LIQUID_TOP if uni == "S200" else None)
            r = pf.row(f"{uni} {mode}", sim["curve"], start, split, end,
                       {"trades": len(sim["trades"]), "trade_stats": stats(sim["trades"]),
                        "exposure_pct": sim["exposure_pct"]})
            r["verdict"]["beats_nifty"] = (r["full"]["cagr"] or -99) > (rows[1]["full"]["cagr"] or -99)
            rows.append(r)
    s50 = [r for r in rows if r["strategy"].startswith("S50") and r["verdict"]["pass"]]
    chosen = max(s50, key=lambda r: (r["full"]["ratio"] or -99))["strategy"] if s50 else None
    return {"version": VERSION, "registered": "2026-10-21", "start": str(start), "split": str(split), "end": str(end),
            "years": round((end - start).days / 365, 2), "rows": rows, "chosen": chosen,
            "passed": [r["strategy"] for r in rows if (r.get("verdict") or {}).get("pass")],
            "rules": {"pullback_pct": PULLBACK_PCT, "max_open": MAX_OPEN, "slot_pct": SLOT_PCT, "max_hold": MAX_HOLD,
                      "stop_atr": STOP_ATR, "leaders": UNIVERSES, "weak_modes": WEAK_MODES,
                      "pass_cagr_gt": pf.PASS_CAGR, "pass_max_dd_le": pf.PASS_MAX_DD}}
