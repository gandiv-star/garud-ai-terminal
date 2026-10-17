"""Smart scanner snapshot — every NIFTY 50 stock checked against the pre-registered paper rules.

No composite or "AI" score is invented: the rules are yes/no, so each stock gets a plain
action with its reason:
  BUY CANDIDATE  an active rule signals on the last completed bar -> paper entry at the next open
  OPEN           already held by that rule
  WATCH          the strategy signals, but today's NIFTY regime blocks the rule
  NO TRADE       no rule signals
  DATA ISSUE     the stock's data could not be checked
Reference stop/quantity use the rule's own sizing on the last close (the real entry is the
next open). Stored once per day by the evening automatic run as SCAN_SNAPSHOT.
"""
from backtest import paper_rule
from backtest.backtest_engine import _regime_at
from features.feature_engine import FeatureEngine

VERSION = "scan_v1"
ORDER = {"BUY CANDIDATE": 0, "OPEN": 1, "WATCH": 2, "NO TRADE": 3, "DATA ISSUE": 4}


def build_snapshot(data, registry: dict, trades: list, rules=paper_rule.RULES) -> dict:
    """trades: all rule paper trades (open and closed) from the database."""
    nifty = data.nifty_completed()
    regime = _regime_at([c for _, c in nifty])
    open_by = {(t.strategy_name, t.symbol) for t in trades if t.exit_price is None}
    symbols = sorted({s for r in rules for s in r.universe})
    per_rule, errors = {}, {}
    for r in rules:
        reg, reg_date, sigs, errs = paper_rule.scan(r, registry[r.strategy_name], data)
        per_rule[r.rule_id] = {g.symbol: g for g in sigs}
        for s, e in errs.items():
            errors.setdefault(s, e)
    fe = FeatureEngine()
    rows = []
    for sym in symbols:
        try:
            bars = paper_rule.completed_bars(data.bars(sym), data.now)
            f = fe.compute(sym, bars) if len(bars) >= 25 else None
        except Exception as e:
            f, bars = None, []
            errors.setdefault(sym, str(e))
        checks, action, reason, ref = [], "NO TRADE", "કોઈ rule નો signal નથી", None
        for r in rules:
            if sym not in r.universe:
                continue
            g = per_rule[r.rule_id].get(sym)
            if g is None:
                checks.append({"rule": r.title, "result": "data issue"})
                continue
            why = ""
            try:
                why = registry[r.strategy_name]().evaluate(sym, f, regime).rationale if f else ""
            except Exception:
                pass
            held = (r.rule_id, sym) in open_by
            used = paper_rule.rule_already_used(trades, r.rule_id, sym, g.signal_date) if g.actionable else None
            res = ("open" if held else
                   f"signal ignored: {used}" if used else
                   "signal" if g.actionable else "blocked by regime" if g.strategy_decision == "BUY" else "no signal")
            checks.append({"rule": r.title, "result": res, "why": why})
            cand = "BUY CANDIDATE" if res == "signal" and not held else "OPEN" if held else \
                "WATCH" if res == "blocked by regime" else None
            if cand and ORDER[cand] < ORDER[action]:
                action, reason = cand, f"{r.title}: {why or res}"
                if cand == "BUY CANDIDATE" and g.atr:
                    stop, qty = paper_rule.position_size(r, g.last_close, g.atr)
                    ref = {"rule": r.title, "close": g.last_close, "stop": stop, "qty": qty,
                           "risk": round((g.last_close - stop) * qty, 2)}
        if not checks or all(c["result"] == "data issue" for c in checks):
            action, reason = "DATA ISSUE", errors.get(sym, "no data")
        rows.append({
            "symbol": sym, "action": action, "reason": reason, "checks": checks, "ref": ref,
            "close": round(bars[-1].close, 2) if bars else None,
            "date": str(paper_rule._bar_date(bars[-1])) if bars else None,
            "trend_pct": f.trend_strength if f else None, "mom10_pct": f.momentum if f else None,
            "atr_pct": round(f.atr / f.price * 100, 2) if f and f.atr and f.price else None,
            "rel_volume": f.relative_volume if f else None,
        })
    rows.sort(key=lambda x: (ORDER[x["action"]], x["symbol"]))
    return {"version": VERSION, "regime": regime.regime.value,
            "data_date": str(nifty[-1][0]) if nifty else None, "rows": rows,
            "counts": {k: sum(1 for x in rows if x["action"] == k) for k in ORDER}}
