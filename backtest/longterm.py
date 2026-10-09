"""Long-horizon comparison: can a low-turnover approach beat a bank FD?

Pre-registered (8 Oct 2026, before running). Evaluation: 5 years ending BENCHMARK_END,
TRAIN = first 3 years, TEST = last 2 years. Capital Rs.1,00,000. Real delivery charges
(ChargeModel) on every trade; idle money earns a liquid-fund rate.

Strategies
  A  FD                     7.0% p.a., compounded
  B  NIFTY buy & hold       NIFTYBEES ETF (dividend-adjusted); fallback ^NSEI price index
  C  Regime ETF switch      month-end: NIFTY regime MODERATE_BULL/WEAK_BULL -> 100% ETF,
                            otherwise 100% liquid fund
  D  Momentum top-10        month-end: rank NIFTY 50 by 12-1 momentum (return from 252 to
                            21 trading days ago), hold top 10 equal weight
  E  Momentum + regime      D, but only while the regime is MODERATE_BULL/WEAK_BULL,
                            otherwise 100% liquid fund
  Signals use the month-end close; trades execute at the NEXT trading day's close.
  Positions whose weight changes by < 2% of the portfolio are not traded (cost control).

Verdict per strategy (C, D, E)
  BEATS FD          : CAGR > 7% over the full 5 years AND in TEST
  BETTER THAN INDEX : full-period CAGR/MaxDD higher than buy & hold
  Paper-trade candidate only if both.
Known bias: D/E use TODAY's NIFTY 50 list (survivorship) -> their results are optimistic.
"""
from bisect import bisect_right
from datetime import date, datetime, timedelta

from backtest.backtest_engine import ChargeModel, _nifty_series, _regime_at
from data.yfinance_loader import YFinanceLoader

CAPITAL = 100000.0
FD_RATE, LIQUID_RATE = 0.07, 0.065
EVAL_DAYS, TRAIN_DAYS, LOOKBACK_DAYS = 1825, 3 * 365, 420
MOM_LONG, MOM_SKIP, TOP_N = 252, 21, 10
BULL = ("MODERATE_BULL", "WEAK_BULL")
NO_TRADE_BAND = 0.02
ETF = "NIFTYBEES"
FFILL_MAX = 5   # a stale price older than this many trading days counts as missing


def _d(ts):
    return ts.date() if hasattr(ts, "date") else ts


class Market:
    """Daily closes on the NIFTY trading calendar (forward-filled a few days)."""

    def __init__(self, nifty: list, closes: dict):
        self.dates = [d for d, _ in nifty]
        self.nifty = [c for _, c in nifty]
        self.px = {}
        for sym, series in closes.items():
            out, last, age = [], None, FFILL_MAX + 1
            for d in self.dates:
                if d in series:
                    last, age = series[d], 0
                else:
                    age += 1
                out.append(last if age <= FFILL_MAX else None)
            self.px[sym] = out

    def price(self, sym, i):
        s = self.px.get(sym)
        return s[i] if s is not None else None

    def regime_bull(self, i) -> bool:
        return _regime_at(self.nifty[: i + 1]).regime.value in BULL

    def momentum(self, sym, i):
        if i - MOM_LONG < 0:
            return None
        a, b = self.price(sym, i - MOM_LONG), self.price(sym, i - MOM_SKIP)
        return (b / a - 1) if a and b else None


def load(universe, end_date: date) -> tuple:
    end = datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)
    eval_start = end - timedelta(days=EVAL_DAYS)
    data_start = eval_start - timedelta(days=LOOKBACK_DAYS)
    nifty = _nifty_series(data_start, end)
    loader, closes, errors = YFinanceLoader(), {}, {}
    for sym in list(universe) + [ETF]:
        try:
            bars = loader.get_historical_bars(sym, data_start, end)
            closes[sym] = {_d(b.timestamp): float(b.close) for b in bars}
        except Exception as e:
            errors[sym] = str(e)
    if not closes.get(ETF):
        closes[ETF] = dict(nifty)          # fallback: price index, no dividends
        errors[ETF] = "NIFTYBEES unavailable — used ^NSEI price index"
    return Market(nifty, closes), eval_start.date(), errors


def month_end_indices(dates: list, first_index: int) -> list:
    out = []
    for i in range(first_index, len(dates) - 1):
        if dates[i + 1].month != dates[i].month:
            out.append(i)
    return out


def simulate(mkt: Market, start_i: int, target_fn, rebalance_idx: list) -> tuple:
    """target_fn(i) -> {symbol: weight} decided on day i, executed at i+1's close.
    Returns (curve [(date, value)], trade_count)."""
    cm = ChargeModel()
    units, cash = {}, CAPITAL
    pending, trades = None, 0
    targets = {i + 1: i for i in rebalance_idx}
    curve = []
    for i in range(start_i, len(mkt.dates)):
        if i > start_i:
            days = (mkt.dates[i] - mkt.dates[i - 1]).days
            cash *= (1 + LIQUID_RATE) ** (days / 365)
        # value positions; a position whose price disappears is sold at its last price
        for sym in list(units):
            if mkt.price(sym, i) is None:
                last = next((mkt.price(sym, k) for k in range(i - 1, -1, -1) if mkt.price(sym, k)), 0)
                proceeds = units.pop(sym) * last
                cash += proceeds - cm.sell_charges(proceeds)
        if i in targets:
            pending = target_fn(targets[i])
        if pending is not None:
            value = cash + sum(u * mkt.price(s, i) for s, u in units.items())
            want = {s: w for s, w in pending.items() if w > 0 and mkt.price(s, i)}
            for s in set(units) | set(want):
                p = mkt.price(s, i)
                cur = units.get(s, 0) * p
                diff = want.get(s, 0) * value - cur
                if diff < 0 and (abs(diff) >= NO_TRADE_BAND * value or s not in want):
                    sell = min(-diff, cur)
                    cash += sell - cm.sell_charges(sell)
                    units[s] = units.get(s, 0) - sell / p
                    if units[s] * p < 1:
                        units.pop(s)
                    trades += 1
            buys = {}
            for s, w in want.items():
                p = mkt.price(s, i)
                diff = w * value - units.get(s, 0) * p
                if diff > 0 and (diff >= NO_TRADE_BAND * value or s not in units):
                    buys[s] = diff
            need = sum(buys.values()) * 1.002
            scale = min(1.0, cash / need) if need > 0 else 0.0
            for s, amt in buys.items():
                amt *= scale
                cost = amt + cm.buy_charges(amt)
                if amt <= 0 or cost > cash:
                    continue
                cash -= cost
                units[s] = units.get(s, 0) + amt / mkt.price(s, i)
                trades += 1
            pending = None
        value = cash + sum(u * mkt.price(s, i) for s, u in units.items())
        curve.append((mkt.dates[i], value))
    return curve, trades


def metrics(curve: list, start: date, end: date) -> dict:
    pts = [(d, v) for d, v in curve if start <= d <= end]
    if len(pts) < 2:
        return {"cagr": None, "max_dd": None, "ratio": None, "final": None}
    days = (pts[-1][0] - pts[0][0]).days
    cagr = (pts[-1][1] / pts[0][1]) ** (365 / days) - 1 if days > 0 else 0.0
    peak, dd = pts[0][1], 0.0
    for _, v in pts:
        peak = max(peak, v)
        dd = max(dd, (peak - v) / peak)
    return {"cagr": round(cagr * 100, 2), "max_dd": round(dd * 100, 2),
            "ratio": round(cagr / dd, 2) if dd > 0 else None, "final": round(pts[-1][1], 0)}


def yearly(curve: list) -> dict:
    out, prev = {}, None
    for d, v in curve:
        out.setdefault(d.year, [v, v])[1] = v
    res = {}
    for y in sorted(out):
        start = prev if prev is not None else out[y][0]
        res[y] = round((out[y][1] / start - 1) * 100, 2)
        prev = out[y][1]
    return res


def run(mkt: Market, eval_start: date) -> dict:
    start_i = bisect_right(mkt.dates, eval_start) - 1
    start_i = max(start_i, 0)
    split = mkt.dates[start_i] + timedelta(days=TRAIN_DAYS)
    end = mkt.dates[-1]
    rebal = month_end_indices(mkt.dates, start_i)
    stocks = [s for s in mkt.px if s != ETF]

    def top_momentum(i):
        scored = [(m, s) for s in stocks if (m := mkt.momentum(s, i)) is not None and mkt.price(s, i)]
        scored.sort(reverse=True)
        picks = [s for _, s in scored[:TOP_N]]
        return {s: 1.0 / TOP_N for s in picks}

    strategies = {
        "B Buy & hold": (lambda i: {ETF: 1.0}, [start_i - 1] if start_i > 0 else []),
        "C Regime ETF": (lambda i: {ETF: 1.0} if mkt.regime_bull(i) else {}, [start_i - 1] + rebal),
        "D Momentum top-10": (top_momentum, [start_i - 1] + rebal),
        "E Momentum + regime": (lambda i: top_momentum(i) if mkt.regime_bull(i) else {}, [start_i - 1] + rebal),
    }
    days_total = (end - mkt.dates[start_i]).days
    fd_curve = [(d, CAPITAL * (1 + FD_RATE) ** ((d - mkt.dates[start_i]).days / 365))
                for d in mkt.dates[start_i:]]
    rows = [{"strategy": "A FD 7%", "trades": 0, **_windows(fd_curve, mkt.dates[start_i], split, end),
             "yearly": yearly(fd_curve)}]
    for name, (fn, idx) in strategies.items():
        idx = [i for i in idx if i >= 0]
        sim_start = min([start_i] + [i + 1 for i in idx])
        curve, n = simulate(mkt, sim_start, fn, idx)
        rows.append({"strategy": name, "trades": n,
                     **_windows(curve, mkt.dates[start_i], split, end), "yearly": yearly(curve)})

    bh = next(r for r in rows if r["strategy"].startswith("B"))
    for r in rows:
        if r["strategy"][0] in "CDE":
            beats_fd = (r["full"]["cagr"] or -99) > FD_RATE * 100 and (r["test"]["cagr"] or -99) > FD_RATE * 100
            better = (r["full"]["ratio"] or -99) > (bh["full"]["ratio"] or -99)
            r["beats_fd"], r["better_than_index"] = beats_fd, better
            r["candidate"] = beats_fd and better
    return {"start": str(mkt.dates[start_i]), "split": str(split), "end": str(end),
            "years": round(days_total / 365, 2), "rows": rows}


def _windows(curve, start, split, end) -> dict:
    return {"full": metrics(curve, start, end), "train": metrics(curve, start, split),
            "test": metrics(curve, split, end)}
