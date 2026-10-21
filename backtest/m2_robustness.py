"""M2 robustness check — is Momentum 200 good only at exactly "top 20, monthly"?

Pre-registered 21 Oct 2026, before running. Same data, period (15 years), costs, liquid-fund rate
and weak-market switch as the Engine 1 test (backtest/momentum200.py). Only the settings change:
  top 10 / 15 / 20 / 30 stocks, monthly (keep a holding while it stays in the top 1.5x)
  top 20 rebalanced only at quarter-ends (Mar/Jun/Sep/Dec)
  top 20 without the "keep while in top 30" buffer
PASS per variant = 15-year CAGR > 7% AND max drawdown <= 25% (same bar as before).
ROBUST = at least 4 of the 6 variants pass. Not robust -> M2 stays in paper but is flagged fragile.
Also reported (information only, never a pass/fail condition):
  * Sharpe and Sortino of monthly returns (risk-free = liquid-fund rate 6.5%)
  * bootstrap of the base variant's monthly returns (5,000 resamples): chance the 15-year CAGR
    would have been below the 7% FD, and the 5th-percentile CAGR
  * benchmarks over the same dates where data exists: NIFTY 200 index (^CNX200, price only) and
    the NIFTY 200 Momentum 30 ETF (MOM30IETF, listed 2022) — the "do nothing, buy the fund" option
Still uses today's NIFTY 200 list (survivorship bias) like Engine 1 -> results optimistic.
"""
import math
import random
from bisect import bisect_right
from datetime import date, timedelta

from backtest import longterm as lt
from backtest import momentum200 as m2

VERSION = 1
VARIANTS = (  # name, top_n, keep_rank, quarterly
    ("top10 monthly", 10, 15, False),
    ("top15 monthly", 15, 22, False),
    ("top20 monthly (M2)", 20, 30, False),
    ("top30 monthly", 30, 45, False),
    ("top20 quarterly", 20, 30, True),
    ("top20 no buffer", 20, 20, False),
)
ROBUST_MIN_PASS = 4
BOOTSTRAP_N = 5000
BENCH_TICKERS = {"NIFTY 200 index": "^CNX200", "NIFTY200 Momentum 30 ETF": "MOM30IETF.NS"}


def targets(data, candidates_fn, top_n: int, keep_rank: int):
    held = set()

    def fn(i):
        nonlocal held
        w, held = m2.select(data, i, candidates_fn(data.mkt.dates[i]), held, True, top_n, keep_rank)
        return w
    return fn


def monthly_returns(curve: list) -> list:
    out, prev, last = [], None, None
    for d, v in curve:
        if last is not None and d.month != last[0].month:
            if prev is not None:
                out.append(last[1] / prev - 1)
            prev = last[1]
        last = (d, v)
    if prev is not None and last is not None:
        out.append(last[1] / prev - 1)
    return out


def sharpe_sortino(rets: list, rf_annual: float = lt.LIQUID_RATE) -> tuple:
    if len(rets) < 12:
        return None, None
    rf = (1 + rf_annual) ** (1 / 12) - 1
    ex = [r - rf for r in rets]
    mean = sum(ex) / len(ex)
    sd = math.sqrt(sum((x - mean) ** 2 for x in ex) / (len(ex) - 1))
    down = [min(x, 0.0) for x in ex]
    dd = math.sqrt(sum(x * x for x in down) / len(down))
    return (round(mean / sd * math.sqrt(12), 2) if sd else None,
            round(mean / dd * math.sqrt(12), 2) if dd else None)


def bootstrap(rets: list, years: float, n: int = BOOTSTRAP_N, seed: int = 7) -> dict:
    if len(rets) < 24 or years <= 0:
        return {"p_below_fd": None, "cagr_p5": None, "cagr_median": None}
    rnd, k, cagrs = random.Random(seed), len(rets), []
    for _ in range(n):
        g = 1.0
        for _ in range(k):
            g *= 1 + rets[rnd.randrange(k)]
        cagrs.append(g ** (1 / years) - 1)
    cagrs.sort()
    return {"p_below_fd": round(sum(1 for c in cagrs if c < lt.FD_RATE) / n * 100, 1),
            "cagr_p5": round(cagrs[int(0.05 * n)] * 100, 2), "cagr_median": round(cagrs[n // 2] * 100, 2)}


def series_cagr(series: list, start: date, end: date):
    pts = [(d, v) for d, v in series if start <= d <= end and v]
    if len(pts) < 2 or (pts[-1][0] - pts[0][0]).days < 180:
        return None, None, None
    days = (pts[-1][0] - pts[0][0]).days
    return round(((pts[-1][1] / pts[0][1]) ** (365 / days) - 1) * 100, 2), pts[0][0], pts[-1][0]


def fetch_series(ticker: str, start, end) -> list:
    import yfinance as yf
    df = yf.Ticker(ticker).history(start=start, end=end).dropna(subset=["Close"])
    return [(ts.date(), float(c)) for ts, c in zip(df.index, df["Close"])]


def run(data, eval_start: date, candidates_fn, bench_series: dict | None = None) -> dict:
    mkt = data.mkt
    start_i = max(bisect_right(mkt.dates, eval_start) - 1, 0)
    start, end = mkt.dates[start_i], mkt.dates[-1]
    split = start + timedelta(days=m2.DECADE_DAYS)
    month_ends = lt.month_end_indices(mkt.dates, start_i)
    rows, base_curve, base_rets = [], None, []
    for name, top_n, keep, quarterly in VARIANTS:
        idx = [start_i - 1] + [i for i in month_ends if not quarterly or mkt.dates[i].month in (3, 6, 9, 12)]
        idx = [i for i in idx if i >= 0]
        sim_start = min([start_i] + [i + 1 for i in idx])
        curve, n = lt.simulate(mkt, sim_start, targets(data, candidates_fn, top_n, keep), idx)
        w = lt._windows(curve, start, split, end)
        rets = monthly_returns([(d, v) for d, v in curve if d >= start])
        sh, so = sharpe_sortino(rets)
        r = {"strategy": name, **w, "yearly": lt.yearly(curve), "trades": n, "sharpe": sh, "sortino": so,
             "verdict": m2.verdict(w["full"])}
        rows.append(r)
        if top_n == 20 and keep == 30 and not quarterly:
            base_curve, base_rets = curve, rets
    passed = sum(1 for r in rows if r["verdict"]["pass"])
    years = (end - start).days / 365
    boot = bootstrap(base_rets, years) if base_curve else {}
    bench = []
    for label, series in (bench_series or {}).items():
        b_cagr, b0, b1 = series_cagr(series, start, end)
        if b_cagr is None:
            bench.append({"name": label, "available": False})
            continue
        m_cagr, _, _ = series_cagr(base_curve, b0, b1)
        bench.append({"name": label, "available": True, "from": str(b0), "to": str(b1), "cagr": b_cagr,
                      "m2_cagr_same_period": m_cagr})
    return {"version": VERSION, "registered": "2026-10-21", "start": str(start), "end": str(end),
            "years": round(years, 2), "rows": rows, "passed_count": passed, "robust": passed >= ROBUST_MIN_PASS,
            "bootstrap": boot, "benchmarks": bench,
            "bias_note": "today's NIFTY 200 list: survivorship bias — results optimistic"}
