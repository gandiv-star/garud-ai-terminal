"""Phase 2 — 15-year SHARED-CAPITAL portfolio test (one Rs.1,00,000 account, not one per trade).

Pre-registered 19 Oct 2026, BEFORE running A / A2. Owner decision (19 Oct): keep the bar simple.
Period: 15 years ending rule_report.BENCHMARK_END, point-in-time NIFTY 50 list
(backtest/nifty50_history.py) — only stocks in the index on that day can be bought.

Candidates
  A   v3 swing rule as a real portfolio: Trend Following signal (rule v3: stop 2x ATR, exit after
      40 trading days), entry at the next open, the live guard's limits (max 5 open, max 20% of
      equity per stock, 1% of current equity risked per trade), gap-aware fills + slippage
      (FillModel v2), real delivery charges; idle cash earns the liquid-fund rate (6.5%).
      More signals than free slots -> strongest trend (price vs SMA20) first.
  A2  A + "weak market switch" (owner's idea): when NIFTY's regime is not MODERATE_BULL/WEAK_BULL
      at a close, everything is sold at the next open and no new buys happen until the regime is
      bull again; meanwhile the money earns the liquid-fund rate.
  C / F / G  from the long-term study, recomputed on the same data:
      C NIFTY ETF when bull, else liquid fund · F momentum top-10 monthly (true list)
      G = F + the same weak-market switch.
  B NIFTY buy & hold and FD 7% are shown for comparison.

PASS (each candidate): 15-year CAGR after costs > 7% (FD)  AND  max drawdown <= 25%.
Shown as information only (never a pass/fail condition): decade vs last-5-years CAGR, yearly
returns, share of 2-year windows with a gain, whether it beat NIFTY buy & hold.
Honesty notes: C/F/G results were already known when this bar was set, so their PASS is not an
out-of-sample result; A/A2 had never been run. Delisted stocks that yfinance no longer serves
cannot be traded (makes results somewhat optimistic). PASS = paper-trade candidate, never "profitable".
"""
from bisect import bisect_right
from datetime import date, datetime, timedelta

from backtest import longterm as lt
from backtest.backtest_engine import ChargeModel, FillModel, _nifty_series, _regime_at
from core.constants import Decision
from features.feature_engine import FeatureEngine

VERSION = 1
CAPITAL = 100000.0
LIQUID_RATE = lt.LIQUID_RATE
FD_RATE = lt.FD_RATE
MAX_OPEN, MAX_STOCK_PCT, RISK_PCT = 5, 20.0, 1.0
STOP_ATR, HOLD_DAYS = 2.0, 40
MIN_BARS, FEATURE_WINDOW = 25, 60     # features only use the last ~21 bars; 60 gives identical values
STALE_DAYS = 10                       # a held stock with no bar for this many sessions is sold (delisted)
BULL = ("MODERATE_BULL", "WEAK_BULL")
PASS_CAGR, PASS_MAX_DD = 7.0, 25.0
EVAL_DAYS = 15 * 365 + 4
DECADE_DAYS = 10 * 365 + 2


def _d(ts):
    return ts.date() if hasattr(ts, "date") else ts


def clean_bars(bars: list) -> list:
    """Drops bad ticks (a >2x jump that is undone within 5 days, as in longterm._despike) and
    bars with non-positive prices."""
    bars = [b for b in bars if min(b.open, b.high, b.low, b.close) > 0]
    closes = [b.close for b in bars]
    fixed = lt._despike(closes)
    return [b for b, c, f in zip(bars, closes, fixed) if c == f]


def stitch_bars(primary: list, alias: list) -> list:
    """Older history from a renamed ticker, scaled so the two series join without a jump."""
    if not alias:
        return list(primary)
    if not primary:
        return list(alias)
    first = _d(primary[0].timestamp)
    before = [b for b in alias if _d(b.timestamp) <= first]
    if not before:
        return list(primary)
    ratio = primary[0].close / before[-1].close
    from data.data_loader import Bar
    older = [Bar(b.symbol, b.timestamp, b.open * ratio, b.high * ratio, b.low * ratio, b.close * ratio, b.volume)
             for b in alias if _d(b.timestamp) < first]
    return older + list(primary)


class Universe:
    """Daily bars per symbol, looked up by NIFTY session index."""

    def __init__(self, nifty: list, bars: dict):
        self.dates = [d for d, _ in nifty]
        self.nifty = [c for _, c in nifty]
        self.bars = {}          # sym -> list of bars
        self.at = {}            # sym -> {session index: position in its bar list}
        pos = {d: i for i, d in enumerate(self.dates)}
        for sym, bl in bars.items():
            bl = clean_bars(bl)
            idx = {}
            for k, b in enumerate(bl):
                i = pos.get(_d(b.timestamp))
                if i is not None:
                    idx[i] = k
            if idx:
                self.bars[sym], self.at[sym] = bl, idx

    def bar(self, sym, i):
        k = self.at.get(sym, {}).get(i)
        return self.bars[sym][k] if k is not None else None

    def history(self, sym, i, n):
        k = self.at.get(sym, {}).get(i)
        if k is None:
            return []
        return self.bars[sym][max(0, k - n + 1): k + 1]

    def last_close(self, sym, i):
        """Latest close on or before session i, with how many sessions ago it was."""
        idx = self.at.get(sym, {})
        for j in range(i, max(-1, i - 400), -1):
            if j in idx:
                return self.bars[sym][idx[j]].close, i - j
        return None, None


def simulate(u: Universe, start_i: int, members_fn, strategy_factory, weak_switch: bool = False,
             fill: FillModel | None = None, charges: ChargeModel | None = None) -> dict:
    fill, cm, fe = fill or FillModel(), charges or ChargeModel(), FeatureEngine()
    strategy = strategy_factory()
    cash, pos, pending, exit_all = CAPITAL, {}, [], False
    curve, trades, invested_days = [], [], 0.0

    def equity(i):
        v = cash
        for s, p in pos.items():
            px, _ = u.last_close(s, i)
            v += p["qty"] * (px if px else p["entry"])
        return v

    def close_position(s, price, i, reason):
        nonlocal cash
        p = pos.pop(s)
        gross = p["qty"] * price
        cash += gross - cm.sell_charges(gross)
        net = (price - p["entry"]) * p["qty"] - p["buy_charges"] - cm.sell_charges(gross)
        trades.append({"symbol": s, "entry_date": str(u.dates[p["entry_i"]]), "exit_date": str(u.dates[i]),
                       "entry": round(p["entry"], 2), "exit": round(price, 2), "qty": p["qty"],
                       "net": round(net, 2), "reason": reason})

    for i in range(start_i, len(u.dates)):
        if i > start_i:
            cash *= (1 + LIQUID_RATE) ** ((u.dates[i] - u.dates[i - 1]).days / 365)

        # 1. weak-market switch decided at yesterday's close: sell everything at today's open
        if exit_all:
            for s in list(pos):
                b = u.bar(s, i)
                if b is not None:
                    close_position(s, fill.time_exit_price(b.open), i, "WEAK_MARKET")
            exit_all = False

        # 2. entries decided at yesterday's close, filled at today's open
        if pending:
            eq = equity(i - 1)
            for s, atr in pending:
                if len(pos) >= MAX_OPEN or s in pos:
                    continue
                b = u.bar(s, i)
                if b is None:
                    continue
                price = fill.entry_price(b.open)
                stop = price - (atr * STOP_ATR if atr else price * 0.03)
                if stop <= 0 or price <= stop:
                    continue
                qty = int(eq * RISK_PCT / 100 / (price - stop))
                qty = min(qty, int(eq * MAX_STOCK_PCT / 100 // price))
                while qty > 0 and qty * price + cm.buy_charges(qty * price) > cash:
                    qty -= 1
                if qty <= 0:
                    continue
                bc = cm.buy_charges(qty * price)
                cash -= qty * price + bc
                pos[s] = {"qty": qty, "entry": price, "stop": stop, "entry_i": i, "held": 0, "buy_charges": bc}
            pending = []

        # 3. exits on today's bar (the entry day included, like the backtest engine)
        for s in list(pos):
            p = pos[s]
            b = u.bar(s, i)
            if b is None:
                px, age = u.last_close(s, i)
                if age is not None and age >= STALE_DAYS:
                    close_position(s, fill.time_exit_price(px), i, "NO_DATA")
                continue
            if i > p["entry_i"]:
                p["held"] += 1
            if b.low <= p["stop"]:
                close_position(s, fill.stop_exit_price(b.open, p["stop"]), i,
                               "STOP_GAP" if b.open < p["stop"] else "STOP_LOSS")
            elif p["held"] >= HOLD_DAYS:
                close_position(s, fill.time_exit_price(b.close), i, "TIME_BASED")

        # 4. signals at today's close for tomorrow's open
        if i + 1 < len(u.dates):
            regime = _regime_at(u.nifty[: i + 1])
            weak = regime.regime.value not in BULL
            if weak_switch and weak:
                exit_all = bool(pos)
            elif len(pos) < MAX_OPEN:
                cands = []
                for s in members_fn(u.dates[i]):
                    if s in pos or u.bar(s, i) is None:
                        continue
                    hist = u.history(s, i, FEATURE_WINDOW)
                    if len(hist) < MIN_BARS:
                        continue
                    f = fe.compute(s, hist)
                    try:
                        sig = strategy.evaluate(s, f, regime)
                    except Exception:
                        continue
                    if sig.decision == Decision.BUY:
                        cands.append((-(f.trend_strength or 0), s, f.atr))
                cands.sort()
                pending = [(s, atr) for _, s, atr in cands[: MAX_OPEN - len(pos)]]

        value = equity(i)
        if pos:
            invested_days += (value - cash) / value if value > 0 else 0
        curve.append((u.dates[i], value))

    n = len(curve) or 1
    return {"curve": curve, "trades": trades, "exposure_pct": round(invested_days / n * 100, 1)}


def trade_stats(trades: list) -> dict:
    nets = [t["net"] for t in trades]
    wins, losses = [x for x in nets if x > 0], [x for x in nets if x <= 0]
    return {"count": len(nets), "win_rate": round(len(wins) / len(nets) * 100, 1) if nets else None,
            "pf": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None,
            "gap_stops": sum(1 for t in trades if t["reason"] == "STOP_GAP")}


def two_year_windows(curve: list) -> dict:
    """Share of consecutive 2-year windows that ended with a gain (information only)."""
    if not curve:
        return {"windows": 0, "positive": 0}
    out, start = [], 0
    while start < len(curve):
        end_date = curve[start][0] + timedelta(days=730)
        j = bisect_right([d for d, _ in curve], end_date) - 1
        if j <= start or curve[j][0] < end_date - timedelta(days=10):
            break
        out.append(curve[j][1] > curve[start][1])
        start = j
    return {"windows": len(out), "positive": sum(out)}


def verdict(full: dict) -> dict:
    cagr, dd = full.get("cagr"), full.get("max_dd")
    beats_fd = cagr is not None and cagr > PASS_CAGR
    dd_ok = dd is not None and dd <= PASS_MAX_DD
    return {"beats_fd": beats_fd, "dd_ok": dd_ok, "pass": beats_fd and dd_ok}


def row(name: str, curve: list, start: date, split: date, end: date, extra: dict | None = None) -> dict:
    w = lt._windows(curve, start, split, end)
    return {"strategy": name, **w, "yearly": lt.yearly(curve), "two_year": two_year_windows(curve),
            "verdict": verdict(w["full"]), **(extra or {})}


def load(symbols, end_date: date, aliases: dict, loader=None, nifty=None, eval_days: int = EVAL_DAYS):
    """Downloads NIFTY and every symbol once. Returns (Universe, closes for longterm, eval_start, errors)."""
    end = datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)
    eval_start = end - timedelta(days=eval_days)
    data_start = eval_start - timedelta(days=lt.LOOKBACK_DAYS)
    if nifty is None:
        nifty = _nifty_series(data_start, end)
    if loader is None:
        from data.yfinance_loader import YFinanceLoader
        loader = YFinanceLoader()
    bars, errors = {}, {}

    def fetch(sym):
        try:
            return loader.get_historical_bars(sym, data_start, end), None
        except Exception as e:
            return [], str(e)

    for sym in list(symbols) + [lt.ETF]:
        bl, err = fetch(sym)
        for alt in aliases.get(sym, ()):
            if bl and _d(bl[0].timestamp) <= _d(data_start) + timedelta(days=30):
                break
            alt_bl, _ = fetch(alt)
            if alt_bl:
                bl = stitch_bars(bl, alt_bl)
        if bl:
            bars[sym] = bl
        else:
            errors[sym] = (err or "no data")[:120]
    closes = {s: {_d(b.timestamp): float(b.close) for b in bl} for s, bl in bars.items()}
    if not closes.get(lt.ETF):
        closes[lt.ETF] = dict(nifty)
        errors[lt.ETF] = "NIFTYBEES unavailable — used ^NSEI price index"
    stock_bars = {s: bl for s, bl in bars.items() if s != lt.ETF}
    return Universe(nifty, stock_bars), lt.Market(nifty, closes), eval_start.date(), errors


def run(u: Universe, mkt, eval_start: date, members_fn, strategy_factory, current=()) -> dict:
    start_i = max(bisect_right(u.dates, eval_start) - 1, 0)
    start, end = u.dates[start_i], u.dates[-1]
    split = start + timedelta(days=DECADE_DAYS)
    rows = []
    for name, switch in (("A v3 swing portfolio", False), ("A2 v3 swing + weak-market switch", True)):
        sim = simulate(u, start_i, members_fn, strategy_factory, weak_switch=switch)
        rows.append(row(name, sim["curve"], start, split, end,
                        {"trades": len(sim["trades"]), "trade_stats": trade_stats(sim["trades"]),
                         "exposure_pct": sim["exposure_pct"], "last_trades": sim["trades"][-5:]}))
    lt_res = lt.run(mkt, eval_start, current=set(current) if current else None, members_fn=members_fn,
                    train_days=DECADE_DAYS)
    keep = {"A": "FD 7%", "B": "NIFTY buy & hold", "C": "C NIFTY ETF + weak-market switch",
            "F": "F Momentum top-10 (true list)", "G": "G Momentum + weak-market switch (true list)"}
    for r in lt_res["rows"]:
        k = r["strategy"][0]
        if k in keep:
            rows.append({"strategy": keep[k], "full": r["full"], "train": r["train"], "test": r["test"],
                         "yearly": r["yearly"], "trades": r["trades"],
                         **({"verdict": verdict(r["full"])} if k in "CFG" else {})})
    bh = next((r for r in rows if r["strategy"] == "NIFTY buy & hold"), None)
    for r in rows:
        if "verdict" in r and bh:
            r["verdict"]["beats_nifty"] = (r["full"]["cagr"] or -99) > (bh["full"]["cagr"] or -99)
    passed = [r["strategy"] for r in rows if (r.get("verdict") or {}).get("pass")]
    return {"version": VERSION, "registered": "2026-10-19", "start": str(start), "split": str(split),
            "end": str(end), "years": round((end - start).days / 365, 2), "rows": rows, "passed": passed,
            "rules": {"pass_cagr_gt": PASS_CAGR, "pass_max_dd_le": PASS_MAX_DD, "max_open": MAX_OPEN,
                      "max_stock_pct": MAX_STOCK_PCT, "risk_pct": RISK_PCT, "hold_days": HOLD_DAYS,
                      "fills": FillModel().describe(), "liquid_rate": LIQUID_RATE}}
