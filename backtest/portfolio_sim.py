"""Portfolio simulation: the paper-trading rules running TOGETHER on ONE pool of capital.

Single-rule backtests give every stock its own full capital, which hides two things
that matter for live trading: how much cash is really needed, and how deep the
combined drawdown gets when many positions are open at once.

Model (daily, long-only, cash delivery):
  * candidate trades come from the same BacktestEngine run as the rule benchmarks
    (same signals, entry at next open, stop / time exit), base sizing Rs.1,00,000 @ 1%;
  * each candidate is re-sized to the portfolio: qty = base_qty x (equity / 1,00,000),
    i.e. the same 1% risk of CURRENT equity, then cut to the cash available;
  * an entry is skipped when max open positions is reached, the stock is already
    held (by any rule), or there isn't cash for even one share — skips are counted;
  * exits are processed before entries each day; charges via ChargeModel;
  * equity is marked to each day's close, so drawdown is the real day-by-day one.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from backtest.backtest_engine import BacktestEngine, ChargeModel, _load_universe

BASE_CAPITAL = 100000.0


@dataclass
class SimTrade:
    rule_id: str
    symbol: str
    entry_date: object      # date
    exit_date: object       # date
    entry_price: float
    exit_price: float
    base_qty: int


@dataclass
class SimResult:
    start_capital: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    trades_taken: int
    skipped: dict
    max_open_positions: int
    avg_invested_pct: float
    per_rule: list
    equity_curve: list = field(default_factory=list)   # [(date, equity)]


def _d(x):
    return x.date() if hasattr(x, "date") else x


def collect_trades(rules, registry: dict, end_date, days: int = 1825, progress=None):
    """Runs each rule over its universe once. Returns (trades, closes) where closes is
    {symbol: {date: close}} for marking positions to market."""
    end = datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)
    start = end - timedelta(days=days)
    symbols = sorted({s for r in rules for s in r.universe})
    _nifty, data, _errors = _load_universe(symbols, start, end)
    nifty = _nifty
    caches = {s: {} for s in data}
    engine = BacktestEngine(ChargeModel())
    trades = []
    total = sum(len(r.universe) for r in rules)
    done = 0
    for rule in rules:
        for sym in rule.universe:
            done += 1
            if progress:
                progress(done, total, f"{rule.title}: {sym}")
            if sym not in data:
                continue
            try:
                res = engine.run(
                    sym, start, end, capital=BASE_CAPITAL, max_holding_days=rule.max_holding_days,
                    stop_atr_multiplier=rule.stop_atr_multiplier, risk_pct_per_trade=rule.risk_pct,
                    strategy=registry[rule.strategy_name](), nifty_series=nifty, bars=data[sym],
                    features_cache=caches[sym], allowed_regimes=set(rule.allowed_regimes),
                )
            except Exception:
                continue
            for t in res.trades:
                if t.quantity > 0:
                    trades.append(SimTrade(rule.rule_id, sym, _d(t.entry_date), _d(t.exit_date),
                                           float(t.entry_price), float(t.exit_price), int(t.quantity)))
    closes = {s: {_d(b.timestamp): float(b.close) for b in bars} for s, bars in data.items()}
    return trades, closes


def simulate(trades: list, closes: dict, capital: float, max_positions: int = 10,
             rule_order: list | None = None) -> SimResult:
    cm = ChargeModel()
    order = {rid: i for i, rid in enumerate(rule_order or [])}
    entries = {}
    for t in trades:
        entries.setdefault(t.entry_date, []).append(t)
    days = sorted({d for c in closes.values() for d in c} | set(entries)
                  | {t.exit_date for t in trades})
    if not days:
        return SimResult(capital, capital, 0.0, 0.0, 0.0, 0, {}, 0, 0.0, [], [])

    cash, equity = capital, capital
    open_pos = {}            # symbol -> dict(trade, qty)
    last_close = {}
    skipped = {"max_positions": 0, "already_held": 0, "no_cash": 0}
    per_rule = {}
    peak, max_dd = capital, 0.0
    max_open, invested_sum, n_days = 0, 0.0, 0
    curve = []

    def close_due(day):
        nonlocal cash
        for sym in [s for s, p in open_pos.items() if p["trade"].exit_date <= day]:
            p = open_pos.pop(sym)
            t, qty = p["trade"], p["qty"]
            proceeds = t.exit_price * qty
            sell_ch = cm.sell_charges(proceeds)
            cash += proceeds - sell_ch
            pnl = (t.exit_price - t.entry_price) * qty - p["buy_charges"] - sell_ch
            r = per_rule.setdefault(t.rule_id, {"trades": 0, "net_pnl": 0.0, "wins": 0})
            r["trades"] += 1
            r["net_pnl"] += pnl
            r["wins"] += 1 if pnl > 0 else 0

    for day in days:
        # 1) exits first (as in the backtest)
        close_due(day)
        # 2) entries, sized on yesterday's equity
        for t in sorted(entries.get(day, []), key=lambda x: (order.get(x.rule_id, 99), x.symbol)):
            if t.symbol in open_pos:
                skipped["already_held"] += 1
                continue
            if len(open_pos) >= max_positions:
                skipped["max_positions"] += 1
                continue
            qty = int(t.base_qty * equity / BASE_CAPITAL)
            unit = t.entry_price * (1 + 0.002)          # leave room for buy charges
            qty = min(qty, int(cash / unit)) if unit > 0 else 0
            if qty <= 0:
                skipped["no_cash"] += 1
                continue
            cost = t.entry_price * qty
            buy_ch = cm.buy_charges(cost)
            cash -= cost + buy_ch
            open_pos[t.symbol] = {"trade": t, "qty": qty, "buy_charges": buy_ch}
        close_due(day)   # a stop hit on the entry day itself
        # 3) mark to market
        for s in open_pos:
            px = closes.get(s, {}).get(day)
            if px is not None:
                last_close[s] = px
        invested = sum(p["qty"] * last_close.get(s, p["trade"].entry_price) for s, p in open_pos.items())
        equity = cash + invested
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100 if peak > 0 else 0.0)
        max_open = max(max_open, len(open_pos))
        invested_sum += invested / equity * 100 if equity > 0 else 0.0
        n_days += 1
        curve.append((day, round(equity, 2)))

    years = max((days[-1] - days[0]).days / 365.25, 1e-9)
    total_ret = (equity / capital - 1) * 100
    cagr = ((equity / capital) ** (1 / years) - 1) * 100 if equity > 0 else -100.0
    return SimResult(
        start_capital=capital, final_equity=round(equity, 2), total_return_pct=round(total_ret, 2),
        cagr_pct=round(cagr, 2), max_drawdown_pct=round(max_dd, 2),
        trades_taken=sum(r["trades"] for r in per_rule.values()) + len(open_pos),
        skipped=skipped, max_open_positions=max_open,
        avg_invested_pct=round(invested_sum / n_days, 1) if n_days else 0.0,
        per_rule=[{"rule_id": rid, "trades": r["trades"], "net_pnl": round(r["net_pnl"], 2),
                   "win_rate_%": round(r["wins"] / r["trades"] * 100, 1) if r["trades"] else 0.0}
                  for rid, r in sorted(per_rule.items())],
        equity_curve=curve,
    )
