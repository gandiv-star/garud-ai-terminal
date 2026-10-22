"""AI/ML Lab — synthetic data; checks walk-forward has no look-ahead and the decision rule."""
from datetime import date

from helpers import bar, trading_days

from backtest import longterm as lt
from backtest import ml_lab as ml
from backtest import momentum200 as m2

DAYS = trading_days(date(2016, 1, 4), 2200)
SYMS = [f"S{i:02d}" for i in range(45)]


def _series(sym):
    import random
    rnd, out = random.Random(sym), []
    p = 100.0
    drift = 0.0008 if int(sym[1:]) % 5 == 0 else 0.0002
    for d in DAYS:
        o = p
        p = o * (1 + drift + rnd.gauss(0, 0.013))
        out.append(bar(d, o, max(o, p) * 1.003, min(o, p) * 0.997, p, sym, 60000))
    return out


class Loader:
    def get_historical_bars(self, sym, start, end, interval="1d"):
        return [b for b in _series(sym) if start.date() <= b.timestamp.date() < end.date()]


def _data():
    nifty = [(d, 20000 * 1.0004 ** i) for i, d in enumerate(DAYS)]
    return m2.load(SYMS, DAYS[-1], {}, loader=Loader(), nifty=nifty, eval_days=8 * 365)


class SpyModel:
    def fit(self, X, y):
        pass

    def predict(self, X):
        return [x[3] for x in X]          # score = 12-1 momentum feature


def test_walk_forward_never_uses_future_labels():
    """Labels are replaced by the session index where each label becomes known; every training
    set must contain only labels known on or before the month-end it predicts for."""
    data, start, _ = _data()
    mkt = data.mkt
    i0 = max(ml.bisect_right(mkt.dates, start) - 1, 0)
    mes = lt.month_end_indices(mkt.dates, i0)
    samples = ml.build_samples(data, mes, lambda d: SYMS)
    for k, i in enumerate(mes):
        syms, xs, ys = samples[i]
        if ys is not None:
            end = mes[k + 1] + 1
            samples[i] = (syms, xs, [end] * len(syms))
    fits = []

    class Recorder(SpyModel):
        def fit(self, X, y):
            fits.append(max(y))
    old = ml.RETRAIN_MONTHS
    ml.RETRAIN_MONTHS = 1
    try:
        preds = ml.walk_forward_scores(samples, mes, mes[30], lambda: Recorder())
    finally:
        ml.RETRAIN_MONTHS = old
    order = sorted(preds)
    assert len(fits) == len(order) > 10
    assert all(f <= i for f, i in zip(fits, order)), list(zip(fits, order))[:5]


def test_run_rows_and_adopt_rule():
    data, start, _ = _data()
    res = ml.run(data, start, lambda d: SYMS, model_fn=lambda: SpyModel())
    names = [r["strategy"] for r in res["rows"]]
    assert names == ["FD 7%", "NIFTY buy & hold", "M2 rule (top 20 momentum)", "ML picker (gradient-boosted trees)"]
    rule, mlr = res["rows"][2]["full"], res["rows"][3]["full"]
    expect = (mlr["cagr"] >= rule["cagr"] + ml.ADOPT_MARGIN_PCT) and mlr["max_dd"] <= ml.MAX_DD
    assert res["adopt_ml"] == expect and res["months_predicted"] > 12


def test_real_model_trains():
    data, start, _ = _data()
    res = ml.run(data, start, lambda d: SYMS)
    assert res["rows"][3]["trades"] > 0 and res["top_quintile_hit_rate"] is not None


def test_research_card():
    import garud_research as gr
    c = gr.ml_lab_summary({"adopt_ml": False, "rows": [{"strategy": "x", "full": {"cagr": 1, "max_dd": 2}}],
                           "top_quintile_hit_rate": 55.0})
    assert not c["pass"] and "M2" in c["verdict"] and len(c["lines"]) == 2
    assert [k for k, _, _ in gr.study_cards({})][:4] == ["PAPER_REPLAY", "COST_RECHECK", "TAX_STUDY", "ML_LAB"]
