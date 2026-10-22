"""Paper replay — runs the REAL momentum paper engine (backtest/momentum_paper.py: whole shares,
paper capital, Upstox 2026 charges, signal at the month-end close, fill at the next session's close,
liquid fund when NIFTY is weak) over the last ~24 months of real prices, month by month, and compares
it with the backtest engine (fractional units) over exactly the same dates and the same charges.

Registered 22 Oct 2026, before running. It answers the first half of the Feb 2027 question —
"does the paper engine behave like the backtest?" — today. The second half ("will the future market
behave like the past?") can only be answered by the forward paper test from 2 Nov 2026.
ENGINE OK (per portfolio) = |paper CAGR - backtest CAGR| <= 2 percentage points per year
AND average idle cash while invested <= 10% of the account.
Information only: nothing is written to the paper portfolios and no rule changes. The M2 universe is
still today's NIFTY 200 list (survivorship bias) — the same for both engines, so the comparison is fair.
"""
from bisect import bisect_right

from backtest import longterm as lt
from backtest import momentum200 as m2
from backtest import momentum_paper as mp
from backtest import tax_study as ts
from backtest.backtest_engine import upstox_delivery_2026

VERSION = 1
REPLAY_DAYS = 740
MAX_GAP_PP, MAX_IDLE_CASH_PCT = 2.0, 10.0
PORTFOLIOS = (("M2", 300000.0), ("G", 100000.0), ("M2", 100000.0))   # last row: M2 at Rs.1 lakh (information)


def _cagr(v0, v1, d0, d1):
    days = (d1 - d0).days
    return round(((v1 / v0) ** (365 / days) - 1) * 100, 2) if days > 0 and v0 > 0 and v1 > 0 else None


def _max_dd(curve):
    peak, dd = None, 0.0
    for _, v in curve:
        peak = v if peak is None else max(peak, v)
        dd = max(dd, (peak - v) / peak * 100 if peak else 0.0)
    return round(dd, 2)


def _monthly(curve):
    out, last = {}, {}
    for d, v in curve:
        last[(d.year, d.month)] = v
    keys = sorted(last)
    return {k: last[k] / last[p] - 1 for p, k in zip(keys, keys[1:])}


def replay_paper(data, pid: str, capital: float, start_i: int, decide_fn) -> dict:
    """Month-by-month replay with momentum_paper.rebalance. Returns curve and stats."""
    mkt = data.mkt
    cm = upstox_delivery_2026()
    st = {**mp.initial_state(pid), "cash": capital, "value": capital, "capital": capital}
    held = set()
    rebal = set(i for i in lt.month_end_indices(mkt.dates, start_i) if i + 1 < len(mkt.dates))
    curve, idle, trades, weak_months, months = [], [], 0, 0, 0
    for i in range(start_i, len(mkt.dates)):
        day = mkt.dates[i]
        if (i - 1) in rebal:                         # fill day = the session after a month-end
            want, held = decide_fn(data, pid, i - 1, held)
            syms = set(want) | set(st.get("units") or {})
            prices = {s: mkt.price(s, i) for s in syms if mkt.price(s, i)}
            st = mp.rebalance(st, prices, want, day, cm=cm)
            trades += len(st["trades"])
            months += 1
            if not want:
                weak_months += 1
            elif st["value"] > 0:
                idle.append(st["cash"] / st["value"] * 100)
        if st.get("as_of"):
            px = {s: mkt.price(s, i) for s in (st.get("units") or {})}
            curve.append((day, mp.mark(st, {k: v for k, v in px.items() if v}, day)))
        else:
            curve.append((day, capital))
    return {"curve": curve, "trades": trades, "months": months, "weak_months": weak_months,
            "avg_idle_cash_pct": round(sum(idle) / len(idle), 1) if idle else 0.0}


def run(data, eval_start, decide_fn, candidates_fn, members_fn, portfolios=PORTFOLIOS) -> dict:
    mkt = data.mkt
    start_i = max(bisect_right(mkt.dates, eval_start) - 1, 0)
    start, end = mkt.dates[start_i], mkt.dates[-1]
    rebal = [i for i in lt.month_end_indices(mkt.dates, start_i)]
    rows = []
    for pid, cap in portfolios:
        paper = replay_paper(data, pid, cap, start_i, decide_fn)
        fn = (m2.momentum_targets(data, candidates_fn, True) if pid == "M2"
              else (lambda i: m2.g_weights(mkt, i, members_fn)))
        first_fill = rebal[0] + 1 if rebal else start_i
        bt = ts.simulate_taxed(mkt, first_fill, fn, rebal, taxed=False, capital=cap, charges=upstox_delivery_2026())
        pc = [(d, v) for d, v in paper["curve"] if d >= mkt.dates[first_fill]]
        bc = [(d, v) for d, v in bt["curve"] if d >= mkt.dates[first_fill]]
        p_cagr = _cagr(pc[0][1], pc[-1][1], pc[0][0], pc[-1][0]) if len(pc) > 1 else None
        b_cagr = _cagr(bc[0][1], bc[-1][1], bc[0][0], bc[-1][0]) if len(bc) > 1 else None
        pm, bm = _monthly(pc), _monthly(bc)
        common = [k for k in pm if k in bm]
        diffs = [abs(pm[k] - bm[k]) * 100 for k in common]
        gap = round(p_cagr - b_cagr, 2) if p_cagr is not None and b_cagr is not None else None
        ok = (gap is not None and abs(gap) <= MAX_GAP_PP and paper["avg_idle_cash_pct"] <= MAX_IDLE_CASH_PCT)
        rows.append({"portfolio": pid, "capital": cap, "paper_cagr": p_cagr, "backtest_cagr": b_cagr, "gap_pp": gap,
                     "paper_final": round(pc[-1][1]) if pc else None, "backtest_final": round(bc[-1][1]) if bc else None,
                     "paper_max_dd": _max_dd(pc), "backtest_max_dd": _max_dd(bc),
                     "avg_idle_cash_pct": paper["avg_idle_cash_pct"], "paper_trades": paper["trades"],
                     "months": paper["months"], "weak_months": paper["weak_months"],
                     "avg_monthly_diff_pp": round(sum(diffs) / len(diffs), 2) if diffs else None,
                     "engine_ok": ok})
    n = [(d, c) for d, c in zip(mkt.dates, mkt.px.get(lt.ETF, mkt.nifty)) if d >= start and c]
    nifty_cagr = _cagr(n[0][1], n[-1][1], n[0][0], n[-1][0]) if len(n) > 1 else None
    return {"version": VERSION, "registered": "2026-10-22", "start": str(start), "end": str(end),
            "years": round((end - start).days / 365, 2), "rows": rows, "nifty_etf_cagr": nifty_cagr,
            "fd_cagr": lt.FD_RATE * 100,
            "note": "Same prices, same charges, same rule; only whole shares + paper capital differ. "
                    "M2 universe = today's NIFTY 200 list (both engines)."}
