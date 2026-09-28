"""Pre-registered paper-trading rules, run fully automatically.

The rules below are FIXED. Changing any value means creating a new rule with a
new rule_id — trades of different rules are never mixed.

The same code is used by:
  * backtest/run_rule_paper.py (GitHub Actions, several times every weekday) — the
    only place that WRITES trades (entries and exits);
  * streamlit_app.py            — read-only view of signals, open trades and stats.

Execution model (identical to BacktestEngine.run):
  * signal on the last COMPLETED daily bar (NIFTY regime from closes up to that day);
  * entry at the NEXT trading day's OPEN (the morning run records today's open);
  * stop = entry - k*ATR(signal day), size = capital*risk% / (entry - stop);
  * exit: stop if any bar from the entry day on trades at/below the stop (exit at
    the stop), else at the close of the Nth completed trading day after entry.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone

from backtest.backtest_engine import ChargeModel, _nifty_series, _regime_at
from core.constants import Decision
from data.yfinance_loader import YFinanceLoader
from database.models import AuditEvent, TradeRecord
from features.feature_engine import FeatureEngine

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_OPEN_IST = time(9, 15)
MARKET_CLOSE_IST = time(15, 35)
LOOKBACK_DAYS = 420

UNIVERSE_8 = ("HDFCBANK", "TCS", "SUNPHARMA", "MARUTI", "TATASTEEL", "HINDUNILVR", "RELIANCE", "DLF")

# NIFTY 50 constituents as known on 28 Sep 2026 (list of 8 Dec 2025, with BSE
# replacing WIPRO from 30 Sep 2026). Frozen: later index changes do NOT alter it.
UNIVERSE_NIFTY50 = (
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO",
    "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL", "BSE", "CIPLA", "COALINDIA",
    "DRREDDY", "EICHERMOT", "ETERNAL", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDIGO", "INFY", "ITC", "JIOFIN",
    "JSWSTEEL", "KOTAKBANK", "LT", "M&M", "MARUTI", "MAXHEALTH", "NESTLEIND", "NTPC",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA",
    "TCS", "TATACONSUM", "TMPV", "TATASTEEL", "TECHM", "TITAN", "TRENT", "ULTRACEMCO",
)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    universe: tuple
    registered_on: str
    strategy_name: str = "Volatility Expansion"
    allowed_regimes: tuple = ("WEAK_BEAR", "SIDEWAYS")
    stop_atr_multiplier: float = 2.0
    max_holding_days: int = 10
    risk_pct: float = 1.0
    capital: float = 100000.0
    target_trades: int = 30

    def describe(self) -> str:
        return (
            f"{self.strategy_name} on {len(self.universe)} stocks | new entries only when NIFTY regime is "
            f"{' or '.join(self.allowed_regimes)} | entry next open | stop {self.stop_atr_multiplier}x ATR | "
            f"exit after {self.max_holding_days} trading days | risk {self.risk_pct}% of "
            f"Rs.{self.capital:,.0f} | registered {self.registered_on} | verdict after {self.target_trades} trades"
        )


RULE_V1 = Rule("volatility_expansion_rule_v1", "v1 — 8 stocks", UNIVERSE_8, "2026-09-27")
RULE_V2 = Rule("volatility_expansion_rule_v2_nifty50", "v2 — NIFTY 50", UNIVERSE_NIFTY50, "2026-09-28")
RULES = (RULE_V1, RULE_V2)
RULE_IDS = {r.rule_id for r in RULES}


# ---------------------------------------------------------------- time helpers
def now_ist() -> datetime:
    return datetime.now(IST)


def _to_ist_date(ts: datetime):
    """DB timestamps are UTC; Postgres/SQLite return them without tzinfo."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(IST).date()


def _bar_date(bar):
    ts = bar.timestamp
    if ts.tzinfo is not None:
        ts = ts.astimezone(IST)
    return ts.date()


def _market_close_utc(d) -> datetime:
    return datetime.combine(d, time(15, 30), IST).astimezone(timezone.utc)


def completed_bars(bars: list, now: datetime) -> list:
    """Drops today's still-forming bar (before the close) so signals always use finished days."""
    if bars and _bar_date(bars[-1]) == now.date() and now.time() < MARKET_CLOSE_IST:
        return bars[:-1]
    return bars


def _valid_price(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x)) and x > 0


# ---------------------------------------------------------------- rule maths
def position_size(rule: Rule, entry_price: float, atr: float | None) -> tuple[float, int]:
    stop_distance = atr * rule.stop_atr_multiplier if atr else entry_price * 0.03
    stop_price = entry_price - stop_distance
    risk_per_share = entry_price - stop_price
    qty = int(rule.capital * (rule.risk_pct / 100) / risk_per_share) if risk_per_share > 0 else 0
    return round(stop_price, 2), qty


def rule_exit(entry_timestamp: datetime, stop_price: float, bars: list, max_holding_days: int,
              now: datetime | None = None):
    """Returns (reason, exit_price, exit_date) or None. Replays every bar since entry."""
    now = now or now_ist()
    entry_date = _to_ist_date(entry_timestamp)
    done = {id(b) for b in completed_bars(bars, now)}
    held = 0
    for b in bars:
        d = _bar_date(b)
        if d < entry_date:
            continue
        if b.low <= stop_price:
            return "STOP_LOSS", round(stop_price, 2), d
        if d > entry_date and id(b) in done:
            held += 1
            if held >= max_holding_days:
                return "TIME_BASED", round(b.close, 2), d
    return None


def rule_already_used(trades: list, rule_id: str, symbol: str, signal_date) -> str | None:
    """Mirrors the backtest: while a position is open (entry day through exit day,
    inclusive) no new signal is evaluated for that symbol, so a signal dated on or
    before a trade's exit day is ignored; one open position per symbol per rule."""
    for t in trades:
        if t.strategy_name != rule_id or t.symbol != symbol:
            continue
        if t.exit_price is None:
            return "open position exists"
        if _to_ist_date(t.timestamp) >= signal_date:
            return "already traded on this signal"
        if t.exit_timestamp is not None and _to_ist_date(t.exit_timestamp) >= signal_date:
            return "signal falls inside a previous position"
    return None


def net_pnl(entry: float, exit_: float, qty: int) -> float:
    cm = ChargeModel()
    charges = cm.buy_charges(entry * qty) + cm.sell_charges(exit_ * qty)
    return round((exit_ - entry) * qty - charges, 2)


def rule_stats(rule: Rule, trades: list) -> dict:
    mine = [t for t in trades if t.strategy_name == rule.rule_id]
    closed = [t for t in mine if t.exit_price is not None and t.realized_pnl is not None]
    wins = [t.realized_pnl for t in closed if t.realized_pnl > 0]
    losses = [t.realized_pnl for t in closed if t.realized_pnl <= 0]
    return {
        "closed": len(closed),
        "open": len(mine) - len(closed),
        "net_pnl": round(sum(t.realized_pnl for t in closed), 2),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None,
        "trades": mine,
    }


# ---------------------------------------------------------------- market data
class MarketData:
    """Downloads each symbol and NIFTY once per run and shares them across rules."""

    def __init__(self, now: datetime):
        self.now = now
        self.end = now.replace(tzinfo=None) + timedelta(days=1)
        self.start = self.end - timedelta(days=LOOKBACK_DAYS)
        self._loader = YFinanceLoader()
        self._bars: dict = {}
        self._nifty = None

    def bars(self, symbol: str) -> list:
        if symbol not in self._bars:
            self._bars[symbol] = self._loader.get_historical_bars(symbol, self.start, self.end)
        return self._bars[symbol]

    def nifty_completed(self) -> list:
        if self._nifty is None:
            series = _nifty_series(self.start, self.end)
            if series and series[-1][0] == self.now.date() and self.now.time() < MARKET_CLOSE_IST:
                series = series[:-1]
            self._nifty = series
        return self._nifty


@dataclass
class RuleSignal:
    symbol: str
    signal_date: object
    last_close: float
    atr: float | None
    strategy_decision: str
    regime: str
    actionable: bool
    note: str


def scan(rule: Rule, strategy_factory, data: MarketData) -> tuple[str, object, list, dict]:
    """Evaluates the rule on the last completed bar. Returns (regime, regime_date, signals, errors)."""
    nifty = data.nifty_completed()
    regime = _regime_at([c for _, c in nifty])
    regime_value = regime.regime.value
    regime_date = nifty[-1][0] if nifty else None
    regime_ok = regime_value in rule.allowed_regimes
    fe = FeatureEngine()
    signals, errors = [], {}
    for sym in rule.universe:
        try:
            bars = completed_bars(data.bars(sym), data.now)
            if len(bars) < 25:
                errors[sym] = "not enough data"
                continue
            if regime_date is not None and _bar_date(bars[-1]) != regime_date:
                errors[sym] = f"last bar {_bar_date(bars[-1])} ≠ NIFTY {regime_date}"
                continue
            features = fe.compute(sym, bars)
            decision = strategy_factory().evaluate(sym, features, regime).decision
            is_buy = decision == Decision.BUY
            note = ("Signal — entry at next open" if is_buy and regime_ok
                    else f"BUY but regime {regime_value} not allowed" if is_buy else "No signal")
            signals.append(RuleSignal(sym, _bar_date(bars[-1]), round(bars[-1].close, 2),
                                      getattr(features, "atr", None), decision.value, regime_value,
                                      is_buy and regime_ok, note))
        except Exception as e:
            errors[sym] = str(e)
    return regime_value, regime_date, signals, errors


# ---------------------------------------------------------------- the daily run
@dataclass
class RunReport:
    started: str
    entries: list = field(default_factory=list)
    exits: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def _audit(db, event_type: str, symbol: str | None, payload: dict) -> None:
    try:
        db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type=event_type,
                                       symbol=symbol, payload=payload))
    except Exception:
        pass  # audit is best-effort; the trade row itself is the record


def process_exits(db, rule: Rule, data: MarketData, trades: list, report: RunReport) -> None:
    for t in trades:
        if t.strategy_name != rule.rule_id or t.exit_price is not None:
            continue
        try:
            rx = rule_exit(t.timestamp, t.stop_price, data.bars(t.symbol), rule.max_holding_days, data.now)
        except Exception as e:
            report.errors.append(f"{rule.rule_id}/{t.symbol} exit check: {e}")
            continue
        if not rx:
            continue
        reason, price, d = rx
        pnl = net_pnl(t.entry_price, price, t.quantity)
        db.update_trade_exit(internal_order_id=t.internal_order_id, exit_price=price,
                             exit_timestamp=_market_close_utc(d), realized_pnl=pnl)
        t.exit_price, t.realized_pnl = price, pnl
        _audit(db, f"RULE_EXIT_{reason}", t.symbol,
               {"rule": rule.rule_id, "exit_date": str(d), "exit_price": price, "net_pnl": pnl})
        report.exits.append(f"{rule.title}: {t.symbol} {reason} {d} @ {price} → Rs.{pnl}")


def process_entries(db, rule: Rule, strategy_factory, data: MarketData, trades: list,
                    report: RunReport) -> None:
    now = data.now
    if not (MARKET_OPEN_IST <= now.time() < MARKET_CLOSE_IST):
        report.notes.append(f"{rule.title}: outside market hours — entries only in the morning runs")
        return
    regime_value, regime_date, signals, errors = scan(rule, strategy_factory, data)
    for sym, err in errors.items():
        report.errors.append(f"{rule.rule_id}/{sym}: {err}")
    if regime_value not in rule.allowed_regimes:
        report.notes.append(f"{rule.title}: NIFTY {regime_value} on {regime_date} — no new entries")
        return
    for g in signals:
        if not g.actionable:
            continue
        blocked = rule_already_used(trades, rule.rule_id, g.symbol, g.signal_date)
        if blocked:
            continue
        today_bar = data.bars(g.symbol)[-1]
        if _bar_date(today_bar) != now.date() or not _valid_price(today_bar.open):
            report.notes.append(f"{rule.title}: {g.symbol} signal — today's open not available yet, retry next run")
            continue
        entry = round(float(today_bar.open), 2)
        stop, qty = position_size(rule, entry, g.atr)
        if qty <= 0:
            report.errors.append(f"{rule.rule_id}/{g.symbol}: size 0 (entry {entry}, stop {stop})")
            continue
        trade = TradeRecord(
            internal_order_id=f"{rule.rule_id}-{g.symbol}-{g.signal_date}", symbol=g.symbol,
            strategy_name=rule.rule_id, strategy_version=rule.registered_on, decision="BUY",
            ai_score=0.0, entry_price=entry, stop_price=stop, target_price=None, quantity=qty,
            risk_amount=round((entry - stop) * qty, 2), regime=g.regime, sector="",
            timestamp=datetime.combine(now.date(), MARKET_OPEN_IST, IST).astimezone(timezone.utc),
        )
        db.save_trade(trade)
        trades.append(trade)
        _audit(db, "RULE_ENTRY", g.symbol, {"rule": rule.rule_id, "signal_date": str(g.signal_date),
                                            "entry": entry, "stop": stop, "qty": qty, "regime": g.regime})
        report.entries.append(f"{rule.title}: {g.symbol} BUY @ {entry} stop {stop} qty {qty}")


def run_all(db, strategy_registry: dict, now: datetime | None = None) -> RunReport:
    now = now or now_ist()
    report = RunReport(started=now.strftime("%Y-%m-%d %H:%M IST"))
    data = MarketData(now)
    trades = [t for t in db.get_trades(limit=5000) if t.strategy_name in RULE_IDS]
    for rule in RULES:
        try:
            process_exits(db, rule, data, trades, report)
        except Exception as e:
            report.errors.append(f"{rule.rule_id} exits: {e}")
        try:
            process_entries(db, rule, strategy_registry[rule.strategy_name], data, trades, report)
        except Exception as e:
            report.errors.append(f"{rule.rule_id} entries: {e}")
    return report
