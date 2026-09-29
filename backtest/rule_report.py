"""Weekly report + pre-registered checkpoints for the automatic paper-trading rules.

Benchmark: each rule is backtested ONCE over the 5 years ending BENCHMARK_END (the
last completed trading day before the rules were registered) with exactly the
rule's settings. The result is stored in the database and never recomputed, so
the yardstick cannot drift.

Checkpoints (fixed 28 Sep 2026), on closed trades in exit order:
  * < 10 trades   : collecting data
  * 10 and 20     : WARNING if the live average net P&L per trade is more than
                    2 standard errors below the benchmark average (z < -2)
  * both 10 and 20 in WARNING -> recommend PAUSE
  * 30 (verdict, on the first 30 trades): PASS only if net > 0, profit factor
    >= 1.15 and z >= -2; otherwise FAIL.
"""
import math
from datetime import date, datetime, timedelta, timezone

from backtest import paper_rule
from backtest.backtest_engine import BacktestEngine, ChargeModel, _load_universe
from database.models import AuditEvent

BENCH_EVENT = "RULE_BENCHMARK"
BENCH_VERSION = 1
BENCHMARK_END = date(2026, 9, 26)
BENCHMARK_DAYS = 1825
Z_WARN = -2.0
PF_PASS = 1.15
CHECKPOINTS = (10, 20)


def _summary(pnls: list) -> dict:
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    mean = sum(pnls) / n if n else 0.0
    std = math.sqrt(sum((p - mean) ** 2 for p in pnls) / (n - 1)) if n > 1 else 0.0
    return {
        "trades": n,
        "net": round(sum(pnls), 2),
        "mean": round(mean, 2),
        "std": round(std, 2),
        "win_rate": round(len(wins) / n * 100, 1) if n else None,
        "pf": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None,
    }


def compute_benchmarks(rules, registry: dict) -> dict:
    end = datetime.combine(BENCHMARK_END, datetime.min.time()) + timedelta(days=1)
    start = end - timedelta(days=BENCHMARK_DAYS)
    symbols = sorted({s for r in rules for s in r.universe})
    nifty, data, _errors = _load_universe(symbols, start, end)
    caches = {s: {} for s in data}  # features don't depend on the strategy: share them
    engine = BacktestEngine(ChargeModel())
    out = {}
    for rule in rules:
        pnls, skipped = [], []
        for sym in rule.universe:
            if sym not in data:
                skipped.append(sym)
                continue
            try:
                res = engine.run(
                    sym, start, end, capital=rule.capital, max_holding_days=rule.max_holding_days,
                    stop_atr_multiplier=rule.stop_atr_multiplier, risk_pct_per_trade=rule.risk_pct,
                    strategy=registry[rule.strategy_name](), nifty_series=nifty, bars=data[sym],
                    features_cache=caches[sym], allowed_regimes=set(rule.allowed_regimes),
                )
                pnls.extend(t.net_pnl for t in res.trades)
            except Exception:
                skipped.append(sym)
        out[rule.rule_id] = {
            **_summary(pnls), "rule_id": rule.rule_id, "version": BENCH_VERSION,
            "period": f"{start.date()} to {BENCHMARK_END}", "skipped": skipped,
        }
    return out


def get_or_create_benchmarks(db, registry: dict) -> dict:
    stored = {}
    for ev in db.get_audit_events(BENCH_EVENT, limit=200):
        p = ev.payload or {}
        if p.get("version") == BENCH_VERSION and p.get("rule_id") not in stored:
            stored[p["rule_id"]] = p
    missing = [r for r in paper_rule.RULES if r.rule_id not in stored]
    if missing:
        for rid, bench in compute_benchmarks(missing, registry).items():
            db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type=BENCH_EVENT,
                                           symbol=None, payload=bench))
            stored[rid] = bench
    return stored


def _pf_ok(s: dict) -> bool:
    """Profit factor test; no losing trade at all counts as passing."""
    if s["pf"] is None:
        return s["net"] > 0
    return s["pf"] >= PF_PASS


def _z(pnls: list, bench: dict) -> float | None:
    if not pnls or not bench.get("std"):
        return None
    se = bench["std"] / math.sqrt(len(pnls))
    return round((sum(pnls) / len(pnls) - bench["mean"]) / se, 2)


def checkpoint_status(closed_pnls: list, bench: dict | None) -> str:
    """closed_pnls must be in exit order."""
    n = len(closed_pnls)
    if not bench:
        return "benchmark not available yet"
    if not bench.get("trades"):
        return "backtest produced no trades for this rule — judged on live PF/net only at 30 trades" if n < 30 else (
            "✅ VERDICT: PASS" if sum(closed_pnls[:30]) > 0 and _pf_ok(_summary(closed_pnls[:30]))
            else "❌ VERDICT: FAIL") + " on first 30 trades (no benchmark)"
    if n < CHECKPOINTS[0]:
        return f"collecting data ({n}/{CHECKPOINTS[0]} for first checkpoint)"
    warns = [k for k in CHECKPOINTS if n >= k and (_z(closed_pnls[:k], bench) or 0) < Z_WARN]
    if n >= 30:
        first = closed_pnls[:30]
        s, z = _summary(first), _z(first, bench)
        ok = s["net"] > 0 and _pf_ok(s) and (z is None or z >= Z_WARN)
        return (f"{'✅ VERDICT: PASS' if ok else '❌ VERDICT: FAIL'} on first 30 trades "
                f"(net Rs.{s['net']}, PF {s['pf']}, z {z})")
    if len(warns) == 2:
        return "⛔ RECOMMEND PAUSE — live results well below backtest at both 10 and 20 trades"
    z_now = _z(closed_pnls, bench)
    if warns:
        return f"⚠️ WARNING at {warns[-1]}-trade checkpoint — live well below backtest (z {z_now})"
    return f"OK — consistent with backtest (z {z_now})"


def weekly_report(db, registry: dict, now: datetime) -> str:
    benches = get_or_create_benchmarks(db, registry)
    trades = db.get_trades(limit=5000)
    week_ago = now.date() - timedelta(days=7)
    lines = [f"📅 Garud weekly report — week ending {now.date()}"]
    for rule in paper_rule.RULES:
        mine = [t for t in trades if t.strategy_name == rule.rule_id]
        closed = sorted([t for t in mine if t.exit_price is not None and t.realized_pnl is not None],
                        key=lambda t: t.exit_timestamp)
        pnls = [t.realized_pnl for t in closed]
        live = _summary(pnls)
        n_open = len(mine) - len(closed)
        entries_w = [t for t in mine if paper_rule._to_ist_date(t.timestamp) > week_ago]
        exits_w = [t for t in closed if paper_rule._to_ist_date(t.exit_timestamp) > week_ago]
        b = benches.get(rule.rule_id, {})
        lines.append("")
        lines.append(f"📊 {rule.title}")
        lines.append(f"Closed {live['trades']}/{rule.target_trades} | open {n_open} | net Rs.{live['net']}"
                     + (f" | win {live['win_rate']}% | PF {live['pf']} | avg Rs.{live['mean']}/trade"
                        if live["trades"] else ""))
        lines.append(f"This week: {len(entries_w)} entries, {len(exits_w)} exits, "
                     f"net Rs.{round(sum(t.realized_pnl for t in exits_w), 2)}")
        if b.get("trades"):
            lines.append(f"Backtest 5y: {b['trades']} trades | avg Rs.{b['mean']}/trade | "
                         f"win {b['win_rate']}% | PF {b['pf']}")
        lines.append(f"Status: {checkpoint_status(pnls, b)}")
    return "\n".join(lines)
