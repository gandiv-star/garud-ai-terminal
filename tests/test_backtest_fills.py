"""A3 — gap-aware stop fills + slippage, and 4 — the Relative Strength NIFTY fix."""
from datetime import date, datetime

from helpers import bar, trading_days

from backtest.backtest_engine import BacktestEngine, ChargeModel, FillModel, _regime_at
from core.constants import Decision, MarketRegime
from features.feature_engine import FeatureSet
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy, StrategySignal
from strategies.relative_strength import RelativeStrengthStrategy

DAYS = trading_days(date(2025, 1, 1), 60)


class BuyOnce(BaseStrategy):
    """Signals BUY on the 30th bar only."""
    name, version = "buy_once", "t"

    def __init__(self):
        self.n = 0

    def evaluate(self, symbol, features, regime):
        self.n += 1
        d = Decision.BUY if self.n == 6 else Decision.NO_TRADE
        return StrategySignal(symbol=symbol, strategy_name=self.name, strategy_version=self.version,
                              decision=d, confidence=1.0, rationale="")


def _bars(gap_open=None):
    """Flat 100 series; entry happens on bar 30 (open 100); bar 33 hits the stop."""
    out = [bar(d, 100, 101, 99, 100) for d in DAYS]
    if gap_open is not None:
        out[33] = bar(DAYS[33], gap_open, gap_open + 0.5, gap_open - 2, gap_open - 1)
    return out


def _run(bars, **kw):
    nifty = [(d, 1000.0) for d in DAYS]
    return BacktestEngine(ChargeModel()).run("X", datetime(2025, 2, 3), datetime(2025, 3, 25),
                                             strategy=BuyOnce(), nifty_series=nifty, bars=bars, **kw)


def _stop(res):
    t = [t for t in res.trades if t.exit_reason == "STOP_LOSS"]
    assert len(t) == 1, res.trades
    return t[0]


def test_legacy_fill_unchanged_stop_at_stop_price_even_on_gap():
    t = _stop(_run(_bars(gap_open=80)))
    # flat bars: ATR 2 -> stop 2 x 2 = 4 below the 100 entry; legacy fills AT 96 although the day opened at 80
    assert t.entry_price == 100.0 and t.exit_price == 96.0 and t.gap_fill is False


def test_default_run_equals_explicit_legacy():
    a, b = _run(_bars(gap_open=80)), _run(_bars(gap_open=80), slippage_pct=0.0, fill_model=None)
    assert [(t.entry_price, t.exit_price, t.net_pnl) for t in a.trades] == \
        [(t.entry_price, t.exit_price, t.net_pnl) for t in b.trades]


def test_gap_aware_fill_at_open_plus_slippage():
    fm = FillModel()
    t = _stop(_run(_bars(gap_open=80), fill_model=fm))
    assert t.gap_fill is True and t.exit_price == round(80 * (1 - fm.stop_slippage_pct / 100), 2)
    assert t.entry_price == round(100 * (1 + fm.entry_slippage_pct / 100), 2)


def test_gap_aware_without_gap_fills_at_stop_minus_slippage():
    fm = FillModel()
    bars = _bars()
    bars[33] = bar(DAYS[33], 99.5, 100, 90, 95)                # opens above the stop, trades through it
    legacy, v2 = _stop(_run(bars)), _stop(_run(bars, fill_model=fm))
    assert legacy.exit_price == 96.0
    # v2: entry 100.05 (slippage), stop 4 below = 96.05, filled 0.10% worse
    assert v2.gap_fill is False and v2.exit_price == round((100.05 - 4) * (1 - fm.stop_slippage_pct / 100), 2)


def test_fill_model_never_better_than_legacy():
    for g in (None, 98, 90, 70):
        legacy = _run(_bars(gap_open=g))
        v2 = _run(_bars(gap_open=g), fill_model=FillModel())
        assert v2.net_pnl <= legacy.net_pnl, g


def test_fill_model_maths():
    fm = FillModel()
    assert fm.stop_exit_price(80, 95) == 80 * 0.999
    assert fm.stop_exit_price(97, 95) == 95 * 0.999
    assert fm.time_exit_price(100) == 100 * 0.9995
    assert fm.describe()["name"] == "gap_aware_v2"


# ------------------------------------------------------------------ Relative Strength fix
def test_regime_at_reports_index_position():
    closes = [1000 * 1.001 ** i for i in range(260)]
    r = _regime_at(closes)
    f = r.supporting_features
    sma50 = sum(closes[-50:]) / 50
    assert abs(f["price_vs_sma50_pct"] - (closes[-1] - sma50) / sma50 * 100) < 1e-3
    assert f["price_vs_sma50_pct"] > 2 and "price_vs_sma200_pct" in f


def test_regime_classification_unchanged_by_the_fix():
    up = [1000 * 1.001 ** i for i in range(300)]
    down = [1000 * 0.999 ** i for i in range(300)]
    assert _regime_at(up).regime == MarketRegime.MODERATE_BULL
    assert _regime_at(down).regime == MarketRegime.WEAK_BEAR
    assert _regime_at(up[:150]).regime == MarketRegime.SIDEWAYS


def _fs(trend):
    return FeatureSet(symbol="X", price=100, trend_strength=trend, momentum=0, atr=1, volatility=0.01)


def test_relative_strength_compares_with_real_nifty():
    rs = RelativeStrengthStrategy()
    strong_index = RegimeAssessment(regime=MarketRegime.MODERATE_BULL, confidence=0.5,
                                    supporting_features={"price_vs_sma50_pct": 4.0})
    flat_index = RegimeAssessment(regime=MarketRegime.MODERATE_BULL, confidence=0.5,
                                  supporting_features={"price_vs_sma50_pct": 0.0})
    # stock +7% vs its average: leads a flat index (7 > 5) but not one that is itself +4% (3 < 5)
    assert rs.evaluate("X", _fs(7.0), flat_index).decision == Decision.BUY
    assert rs.evaluate("X", _fs(7.0), strong_index).decision == Decision.NO_TRADE


def test_relative_strength_gets_index_from_backtest_regime():
    closes = [1000 * 1.001 ** i for i in range(260)]
    reg = _regime_at(closes)
    idx = reg.supporting_features["price_vs_sma50_pct"]
    rs = RelativeStrengthStrategy()
    assert rs.evaluate("X", _fs(idx + 4.0), reg).decision == Decision.NO_TRADE   # was BUY before the fix
    assert rs.evaluate("X", _fs(idx + 6.0), reg).decision == Decision.BUY
