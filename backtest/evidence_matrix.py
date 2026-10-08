"""Regime x Strategy evidence matrix — the evidence base for a "Trading Mode Engine".

Question: does choosing strategies BY MARKET REGIME work out-of-sample in India?

Pre-registered method (fixed 8 Oct 2026, before running):
  * universe: NIFTY 50 (paper_rule.UNIVERSE_NIFTY50); 5 years ending BENCHMARK_END
  * configs: every registered strategy x holding period {10, 40} trading days
    (2.0x ATR stop, 1% risk of Rs.1,00,000, real charges — same engine as everything else)
  * every trade is tagged with the NIFTY regime at entry
  * TRAIN = first 3 years, TEST = last 2 years (never used for any choice)
  * in TRAIN, a (config, regime) cell is FAVOURED if: trades >= 20, net > 0, PF >= 1.15
  * a favoured cell is CONFIRMED if in TEST: trades >= 10, net > 0, PF >= 1.10
  * the Trading Mode idea has evidence only if, in TEST, the trades of all favoured cells
    together have net > 0, PF >= 1.15 AND a higher average net/trade than the
    unconditional baseline (every config, every regime) in TEST.
"""
from datetime import date, datetime, timedelta

from backtest.backtest_engine import BacktestEngine, ChargeModel, _load_universe

HOLDING_DAYS = (10, 40)
TRAIN_DAYS = 3 * 365
TOTAL_DAYS = 1825
MIN_TRAIN_TRADES, MIN_TEST_TRADES = 20, 10
PF_FAVOUR, PF_CONFIRM, PF_MODE = 1.15, 1.10, 1.15
REGIMES = ("MODERATE_BULL", "WEAK_BULL", "SIDEWAYS", "WEAK_BEAR")


def _stats(pnls: list) -> dict:
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    pf = round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else (99.0 if wins else None)
    return {
        "trades": n,
        "net": round(sum(pnls), 2),
        "avg": round(sum(pnls) / n, 2) if n else 0.0,
        "win_rate": round(len(wins) / n * 100, 1) if n else None,
        "pf": pf,
    }


def collect(universe, registry: dict, end_date: date, progress=None):
    """Returns (trades, split_date). trades: list of dicts(config, regime, entry_date, net)."""
    end = datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)
    start = end - timedelta(days=TOTAL_DAYS)
    split = (start + timedelta(days=TRAIN_DAYS)).date()
    nifty, data, _errors = _load_universe(list(universe), start, end)
    engine = BacktestEngine(ChargeModel())
    configs = [(name, hold) for name in registry for hold in HOLDING_DAYS]
    out, done, total = [], 0, len(data) * len(configs)
    for sym, bars in data.items():
        cache = {}  # features depend only on price history: shared by every config
        for name, hold in configs:
            done += 1
            if progress:
                progress(done, total, f"{sym} {name} {hold}d")
            try:
                res = engine.run(sym, start, end, max_holding_days=hold, strategy=registry[name](),
                                 nifty_series=nifty, bars=bars, features_cache=cache)
            except Exception:
                continue
            for t in res.trades:
                d = t.entry_date.date() if hasattr(t.entry_date, "date") else t.entry_date
                out.append({"config": f"{name} | {hold}d", "regime": t.entry_regime or "UNKNOWN",
                            "entry_date": d, "net": float(t.net_pnl)})
    return out, split


def analyse(trades: list, split: date) -> dict:
    train = [t for t in trades if t["entry_date"] < split]
    test = [t for t in trades if t["entry_date"] >= split]
    configs = sorted({t["config"] for t in trades})

    def cell(rows, cfg, reg):
        return _stats([t["net"] for t in rows if t["config"] == cfg and t["regime"] == reg])

    matrix = []
    for cfg in configs:
        for reg in REGIMES:
            tr, te = cell(train, cfg, reg), cell(test, cfg, reg)
            favoured = (tr["trades"] >= MIN_TRAIN_TRADES and tr["net"] > 0
                        and (tr["pf"] or 0) >= PF_FAVOUR)
            confirmed = favoured and (te["trades"] >= MIN_TEST_TRADES and te["net"] > 0
                                      and (te["pf"] or 0) >= PF_CONFIRM)
            matrix.append({"config": cfg, "regime": reg,
                           "train_trades": tr["trades"], "train_pf": tr["pf"], "train_avg": tr["avg"],
                           "test_trades": te["trades"], "test_pf": te["pf"], "test_avg": te["avg"],
                           "favoured": favoured, "confirmed": confirmed})

    fav = {(r["config"], r["regime"]) for r in matrix if r["favoured"]}
    sel = _stats([t["net"] for t in test if (t["config"], t["regime"]) in fav])
    base = _stats([t["net"] for t in test])
    mode_ok = bool(fav) and sel["net"] > 0 and (sel["pf"] or 0) >= PF_MODE and sel["avg"] > base["avg"]

    by_regime = []
    for reg in REGIMES:
        rows = [r for r in matrix if r["regime"] == reg and r["favoured"]]
        by_regime.append({
            "regime": reg,
            "favoured": [r["config"] for r in sorted(rows, key=lambda r: -(r["train_pf"] or 0))],
            "confirmed": [r["config"] for r in rows if r["confirmed"]],
        })

    return {
        "split_date": str(split), "train_trades": len(train), "test_trades": len(test),
        "favoured_cells": len(fav), "confirmed_cells": sum(1 for r in matrix if r["confirmed"]),
        "selection_test": sel, "baseline_test": base, "mode_has_evidence": mode_ok,
        "by_regime": by_regime, "matrix": matrix,
    }
