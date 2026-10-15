"""Intraday (cash, MIS) test on NIFTY 50 with 60-minute bars — can a robot make money intraday?

Pre-registered 15 Oct 2026, before running.
Data: yfinance 60-minute bars, last 720 days (the maximum available free), universe =
paper_rule.UNIVERSE_NIFTY50. Bars start 09:15 IST; a day needs >= 5 bars and a 09:15 first bar.
Every trade: fixed Rs.1,00,000 notional, one trade per stock per strategy per day,
squared off at the close of the day's last bar. Slippage 0.05% per side (adverse).
Charges (typical discount broker, intraday equity): brokerage min(Rs.20, 0.03%) per order,
STT 0.025% on the sell side, exchange 0.00297%, SEBI 0.0001%, stamp 0.003% on the buy side,
GST 18% on brokerage + exchange + SEBI fees.
Inside an hourly bar prices are assumed to move open-low-high-close (up bar) or
open-high-low-close (down bar); a later bar opening beyond the stop exits at that open.

Strategies
  ORB_LONG   opening range = first bar (09:15-10:15). Buy-stop at its high from the 2nd bar
             until the bar starting 13:15; stop = range low; exit at the close.
  ORB_SHORT  mirror: sell-stop at the range low; stop = range high.
  GAP_FADE   |open/prev close - 1| >= 1%: at the open, trade back toward the previous close;
             target = previous close; stop = open +/- gap size; else exit at the close.
  GAP_GO     |gap| >= 1%: at the open, trade in the gap's direction; stop = previous close;
             exit at the close.

Verdict per strategy (both halves of the period must agree):
  PASS if trades >= 200, AND in the first half AND in the second half: net > 0 and PF >= 1.15.
"""
from datetime import datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
DAYS = 720
NOTIONAL = 100000.0
SLIPPAGE = 0.0005
GAP_MIN = 0.01
LAST_ENTRY_BAR = time(13, 15)
MIN_BARS = 5
MIN_TRADES, PF_MIN = 200, 1.15
STRATEGIES = ("ORB_LONG", "ORB_SHORT", "GAP_FADE", "GAP_GO")


def charges(buy_value: float, sell_value: float) -> float:
    brokerage = min(20.0, buy_value * 0.0003) + min(20.0, sell_value * 0.0003)
    exchange = (buy_value + sell_value) * 0.0000297
    sebi = (buy_value + sell_value) * 0.000001
    stt = sell_value * 0.00025
    stamp = buy_value * 0.00003
    gst = (brokerage + exchange + sebi) * 0.18
    return brokerage + exchange + sebi + stt + stamp + gst


def trade_pnl(side: int, entry: float, exit_: float) -> tuple[float, float]:
    """side +1 long / -1 short; prices before slippage. Returns (gross, net) in rupees."""
    e = entry * (1 + SLIPPAGE * side)
    x = exit_ * (1 - SLIPPAGE * side)
    qty = NOTIONAL / e
    gross_raw = (exit_ - entry) * side * qty
    pnl = (x - e) * side * qty
    buy_v, sell_v = (e * qty, x * qty) if side > 0 else (x * qty, e * qty)
    return round(gross_raw, 2), round(pnl - charges(buy_v, sell_v), 2)


def _ist(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(IST)


def group_days(bars: list) -> list:
    """[(date, [bars...])] in date order, only complete-looking sessions."""
    days: dict = {}
    for b in bars:
        t = _ist(b.timestamp)
        days.setdefault(t.date(), []).append((t, b))
    out = []
    for d in sorted(days):
        rows = sorted(days[d], key=lambda r: r[0])
        if len(rows) >= MIN_BARS and rows[0][0].time() == time(9, 15):
            out.append((d, rows))
    return out


def _path(b) -> list:
    """Assumed order of prices inside an hourly bar (standard OHLC convention):
    up bar open-low-high-close, down bar open-high-low-close."""
    return [b.open, b.low, b.high, b.close] if b.close >= b.open else [b.open, b.high, b.low, b.close]


def _orb(rows, side):
    first = rows[0][1]
    level, stop = (first.high, first.low) if side > 0 else (first.low, first.high)
    for k in range(1, len(rows)):
        t, b = rows[k]
        if t.time() > LAST_ENTRY_BAR:
            return None
        pts = _path(b)
        for pos, p in enumerate(pts):
            if (p > level) if side > 0 else (p < level):
                entry = p if pos == 0 else level      # opened beyond the level -> filled at the open
                return _manage(rows, k, side, entry, stop, None, pos + 1)
    return None


def _manage(rows, idx, side, entry, stop, target, start_pos):
    """Walks the price path from the entry point. Stop -> exit at the stop (or at a worse
    opening price of a later bar); target -> exit at the target; else the last bar's close."""
    for k in range(idx, len(rows)):
        pts = _path(rows[k][1])
        for pos in range(start_pos if k == idx else 0, len(pts)):
            p = pts[pos]
            if (p <= stop) if side > 0 else (p >= stop):
                gap_open = pos == 0 and k > idx
                return entry, (p if gap_open else stop), "STOP"
            if target is not None and ((p >= target) if side > 0 else (p <= target)):
                return entry, (p if (pos == 0 and k > idx) else target), "TARGET"
    return entry, rows[-1][1].close, "CLOSE"


def simulate_symbol(symbol: str, bars: list) -> list:
    out = []
    days = group_days(bars)
    for n in range(1, len(days)):
        d, rows = days[n]
        prev_close = days[n - 1][1][-1][1].close
        if (d - days[n - 1][0]).days > 5:          # data hole: no reliable previous close
            prev_close = None
        res = {}
        for side, name in ((1, "ORB_LONG"), (-1, "ORB_SHORT")):
            r = _orb(rows, side)
            if r:
                res[name] = (side,) + r
        if prev_close:
            o = rows[0][1].open
            gap = o / prev_close - 1
            if abs(gap) >= GAP_MIN:
                fade = -1 if gap > 0 else 1
                res["GAP_FADE"] = (fade,) + _manage(rows, 0, fade, o, o + (o - prev_close), prev_close, 1)
                go = -fade
                res["GAP_GO"] = (go,) + _manage(rows, 0, go, o, prev_close, None, 1)
        for name, (side, entry, exit_, reason) in res.items():
            gross, net = trade_pnl(side, entry, exit_)
            out.append({"strategy": name, "symbol": symbol, "date": d, "side": side, "entry": round(entry, 2),
                        "exit": round(exit_, 2), "reason": reason, "gross": gross, "net": net})
    return out


def collect(universe, end: datetime, loader=None, progress=None) -> tuple:
    if loader is None:
        from data.yfinance_loader import YFinanceLoader
        loader = YFinanceLoader()
    start = end - timedelta(days=DAYS)
    trades, errors = [], {}
    for i, sym in enumerate(universe):
        if progress:
            progress(i + 1, len(universe), sym)
        try:
            bars = loader.get_historical_bars(sym, start, end, interval="60m")
            if not bars:
                errors[sym] = "no data"
                continue
            trades += simulate_symbol(sym, bars)
        except Exception as e:
            errors[sym] = str(e)[:80]
    return trades, errors


def stats(rows: list) -> dict:
    nets = [r["net"] for r in rows]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    n = len(nets)
    return {
        "trades": n,
        "net": round(sum(nets), 2),
        "avg": round(sum(nets) / n, 2) if n else 0.0,
        "gross_avg": round(sum(r["gross"] for r in rows) / n, 2) if n else 0.0,
        "win": round(len(wins) / n * 100, 1) if n else None,
        "pf": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else (99.0 if wins else None),
    }


def analyse(trades: list) -> dict:
    dates = sorted({t["date"] for t in trades})
    split = dates[len(dates) // 2] if dates else None
    out = {"first_date": str(dates[0]) if dates else None, "split": str(split) if split else None,
           "last_date": str(dates[-1]) if dates else None, "strategies": {}}
    for s in STRATEGIES:
        rows = [t for t in trades if t["strategy"] == s]
        h1 = stats([t for t in rows if t["date"] < split]) if split else stats([])
        h2 = stats([t for t in rows if t["date"] >= split]) if split else stats([])
        allr = stats(rows)
        ok = lambda h: h["trades"] > 0 and h["net"] > 0 and (h["pf"] or 0) >= PF_MIN  # noqa: E731
        out["strategies"][s] = {"all": allr, "h1": h1, "h2": h2,
                                "pass": allr["trades"] >= MIN_TRADES and ok(h1) and ok(h2)}
    return out
