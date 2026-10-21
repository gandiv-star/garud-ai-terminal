"""AI/ML Lab — can a machine-learning model pick next month's winners better than the M2 rule?

Pre-registered 21 Oct 2026, before running. Same universe, data, costs, liquid-fund rate and
weak-market switch as Engine 1 (backtest/momentum200.py); only the stock PICKER changes.

Model: gradient-boosted trees (scikit-learn HistGradientBoostingRegressor, the same family as
XGBoost/LightGBM) predicting each stock's return over the next month.
Features at a month-end close (all from past prices only): 1, 3, 6 and 12-1 month returns,
60-day volatility, distance from the 52-week high, 6-month traded value (log), and the M2
momentum score. Universe each month: the 150 most liquid eligible stocks (as Engine 1).
Walk-forward, no peeking: the model is retrained every 12 months using only month-ends whose
next-month result was already known; the first 5 years are training only, so the comparison
covers about the last 10 years (out-of-sample for the model).
Portfolio: top 20 by predicted return, equal weight, monthly, keep a holding while it stays in
the predicted top 30 (same as M2), liquid fund when NIFTY is weak.
ADOPT the ML picker only if, over the same out-of-sample years, its CAGR beats M2's by at least
2 percentage points AND its max drawdown <= 25%. Otherwise M2 (simple rule) stays.
Bias: today's NIFTY 200 list (survivorship) affects both the same way.
"""
import math
from bisect import bisect_right
from datetime import date, timedelta

from backtest import longterm as lt
from backtest import momentum200 as m2

VERSION = 1
TRAIN_YEARS, RETRAIN_MONTHS = 5, 12
ADOPT_MARGIN_PCT, MAX_DD = 2.0, 25.0
FEATURES = ("r1", "r3", "r6", "r12_1", "vol60", "from_high", "log_value", "m2_score")


def _px(mkt, s, i):
    return mkt.price(s, i) if 0 <= i < len(mkt.dates) else None


def features(data, i: int, candidates) -> dict:
    """{symbol: feature list} for the liquid eligible universe at month-end index i."""
    mkt = data.mkt
    pool = []
    for s in candidates:
        if s == lt.ETF or not _px(mkt, s, i):
            continue
        si = data.score_inputs(s, i)
        if si:
            pool.append((data.avg_value(s, i), s, si))
    pool.sort(reverse=True)
    pool = pool[: m2.LIQUID_TOP]
    if not pool:
        return {}
    z6 = _z([p[2][0] for p in pool])
    z12 = _z([p[2][1] for p in pool])
    out = {}
    for (val, s, _), a, b in zip(pool, z6, z12):
        p0 = _px(mkt, s, i)
        p = {k: _px(mkt, s, i - k) for k in (21, 63, 126, 252)}
        if not all(p.values()):
            continue
        window = [_px(mkt, s, k) for k in range(i - 60, i + 1)]
        rets = [math.log(y / x) for x, y in zip(window[:-1], window[1:]) if x and y]
        vol = (sum(r * r for r in rets) / len(rets)) ** 0.5 * math.sqrt(252) if rets else 0.0
        high = max(v for v in (_px(mkt, s, k) for k in range(i - 252, i + 1)) if v)
        out[s] = [p0 / p[21] - 1, p0 / p[63] - 1, p0 / p[126] - 1, _px(mkt, s, i - 21) / p[252] - 1, vol,
                  p0 / high - 1, math.log(val + 1.0), (a + b) / 2]
    return out


def _z(vals):
    m = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals)) or 1.0
    return [(v - m) / sd for v in vals]


def make_model():
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                         min_samples_leaf=40, l2_regularization=1.0, random_state=7)


def build_samples(data, month_ends: list, candidates_fn) -> dict:
    """{month-end index: (symbols, X, y or None)}; y = return from the next session's close to the
    session after the next month-end (exactly what the portfolio would have earned)."""
    mkt, out = data.mkt, {}
    for k, i in enumerate(month_ends):
        f = features(data, i, candidates_fn(mkt.dates[i]))
        syms = sorted(f)
        y = None
        if k + 1 < len(month_ends):
            a, b = i + 1, month_ends[k + 1] + 1
            y = []
            for s in syms:
                pa, pb = _px(mkt, s, a), _px(mkt, s, b)
                y.append(pb / pa - 1 if pa and pb else None)
        out[i] = (syms, [f[s] for s in syms], y)
    return out


def walk_forward_scores(samples: dict, month_ends: list, first_oos: int, model_fn=make_model) -> dict:
    """{month-end index: {symbol: predicted return}} for month-ends from first_oos on."""
    preds, model, last_fit = {}, None, None
    for k, i in enumerate(month_ends):
        if i < first_oos:
            continue
        if model is None or k - last_fit >= RETRAIN_MONTHS:
            X, y = [], []
            for j in month_ends[:k - 1] if k >= 1 else []:   # labels of month k-1 end at month k: still unknown
                syms, xs, ys = samples[j]
                for x, t in zip(xs, ys or []):
                    if t is not None:
                        X.append(x)
                        y.append(t)
            if len(X) < 500:
                continue
            model = model_fn()
            model.fit(X, y)
            last_fit = k
        syms, xs, _ = samples[i]
        if syms:
            preds[i] = dict(zip(syms, model.predict(xs)))
    return preds


def ml_targets(data, preds: dict, top_n: int = m2.TOP_N, keep_rank: int = m2.KEEP_RANK):
    held = set()

    def fn(i):
        nonlocal held
        if not data.mkt.regime_bull(i) or i not in preds:
            held = set()
            return {}
        ranked = [s for s, _ in sorted(preds[i].items(), key=lambda x: -x[1])]
        keep = [s for s in ranked[:keep_rank] if s in held]
        picks = keep + [s for s in ranked if s not in keep][: max(0, top_n - len(keep))]
        held = set(picks)
        return {s: 1.0 / top_n for s in picks}
    return fn


def run(data, eval_start: date, candidates_fn, model_fn=make_model) -> dict:
    mkt = data.mkt
    start_i = max(bisect_right(mkt.dates, eval_start) - 1, 0)
    month_ends = lt.month_end_indices(mkt.dates, start_i)
    oos_date = mkt.dates[start_i] + timedelta(days=int(TRAIN_YEARS * 365.25))
    first_oos = next((i for i in month_ends if mkt.dates[i] >= oos_date), None)
    if first_oos is None:
        return {"version": VERSION, "error": "not enough history for an out-of-sample period"}
    samples = build_samples(data, month_ends, candidates_fn)
    preds = walk_forward_scores(samples, month_ends, first_oos, model_fn)
    rebal = [i for i in month_ends if i >= first_oos]
    sim_start = rebal[0] + 1
    start, end = mkt.dates[sim_start], mkt.dates[-1]
    split = start + timedelta(days=max((end - start).days // 2, 1))
    rows = []
    fd = [(d, lt.CAPITAL * (1 + lt.FD_RATE) ** ((d - start).days / 365)) for d in mkt.dates[sim_start:]]
    rows.append({"strategy": "FD 7%", **lt._windows(fd, start, split, end), "trades": 0})
    for name, fn in (("NIFTY buy & hold", lambda i: {lt.ETF: 1.0}),
                     ("M2 rule (top 20 momentum)", m2.momentum_targets(data, candidates_fn, True)),
                     ("ML picker (gradient-boosted trees)", ml_targets(data, preds))):
        idx = rebal[:1] if name.startswith("NIFTY") else rebal
        curve, n = lt.simulate(mkt, sim_start, fn, idx)
        rows.append({"strategy": name, **lt._windows(curve, start, split, end), "yearly": lt.yearly(curve),
                     "trades": n})
    rule, ml = rows[2]["full"], rows[3]["full"]
    adopt = (ml["cagr"] is not None and rule["cagr"] is not None and ml["cagr"] >= rule["cagr"] + ADOPT_MARGIN_PCT
             and (ml["max_dd"] or 99) <= MAX_DD)
    hit = _hit_rate(samples, preds)
    return {"version": VERSION, "registered": "2026-10-21", "start": str(start), "end": str(end),
            "years": round((end - start).days / 365, 2), "rows": rows, "adopt_ml": adopt,
            "months_predicted": len(preds), "top_quintile_hit_rate": hit,
            "bias_note": "today's NIFTY 200 list: survivorship bias — affects both pickers"}


def _hit_rate(samples: dict, preds: dict):
    """Share of months where the model's top-20 picks beat the average stock (information)."""
    wins = total = 0
    for i, p in preds.items():
        syms, _, ys = samples[i]
        if not ys:
            continue
        actual = {s: y for s, y in zip(syms, ys) if y is not None}
        if len(actual) < 40:
            continue
        top = [s for s, _ in sorted(p.items(), key=lambda x: -x[1])[:20] if s in actual]
        if not top:
            continue
        total += 1
        wins += (sum(actual[s] for s in top) / len(top)) > (sum(actual.values()) / len(actual))
    return round(wins / total * 100, 1) if total else None
