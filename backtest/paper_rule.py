"""Pre-registered paper-trading rule (fixed on 27 Sep 2026 — do NOT tune it).

Why this exists: 5 years of backtests found no strategy that passed the pre-set
robustness screen. Volatility Expansion looked profitable only when NIFTY was in
WEAK_BEAR/SIDEWAYS at entry, but that pattern was found AFTER looking at the
data, so it can only be trusted if it holds on NEW trades. This module applies
exactly the same logic as the backtest (same features, same regime rule, same
stop/size/time-exit) so paper results are directly comparable.

Changing any value below creates a NEW rule (new RULE_ID) — old trades must
not be mixed with new ones.
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from backtest.backtest_engine import _nifty_series, _regime_at
from core.constants import Decision
from data.yfinance_loader import YFinanceLoader
from features.feature_engine import FeatureEngine

RULE_ID = "volatility_expansion_rule_v1"
RULE_STRATEGY = "Volatility Expansion"
RULE_REGISTERED_ON = "2026-09-27"
ALLOWED_REGIMES = ("WEAK_BEAR", "SIDEWAYS")
STOP_ATR_MULTIPLIER = 2.0
MAX_HOLDING_DAYS = 10          # trading days after the entry day, exit at that day's close
RISK_PCT = 1.0
PAPER_CAPITAL = 100000.0
TARGET_TRADES = 30             # judge the rule only after this many closed trades

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_CLOSE_IST = time(15, 35)


def now_ist() -> datetime:
    return datetime.now(IST)


def _bar_date(bar):
    ts = bar.timestamp
    if ts.tzinfo is not None:
        ts = ts.astimezone(IST)
    return ts.date()


def _to_ist_date(ts: datetime):
    """DB timestamps are saved in UTC; SQLite returns them without tzinfo, so a
    naive value is treated as UTC before converting to the Indian trading date."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(IST).date()


def completed_bars(bars: list, now: datetime) -> list:
    """Drops today's still-forming daily bar during market hours, so the signal is
    always computed on a finished day — exactly like the backtest."""
    if bars and _bar_date(bars[-1]) == now.date() and now.time() < MARKET_CLOSE_IST:
        return bars[:-1]
    return bars


def rule_description() -> str:
    return (
        f"Strategy: {RULE_STRATEGY} | new entries only when NIFTY regime is "
        f"{' or '.join(ALLOWED_REGIMES)} | stop {STOP_ATR_MULTIPLIER}x ATR | "
        f"time exit after {MAX_HOLDING_DAYS} trading days | risk {RISK_PCT}% of "
        f"Rs.{PAPER_CAPITAL:,.0f} | registered {RULE_REGISTERED_ON} | "
        f"judge after {TARGET_TRADES} closed trades"
    )


def position_size(entry_price: float, atr: float | None) -> tuple[float, int]:
    """Same sizing as BacktestEngine.run: stop = entry - k*ATR (3% fallback),
    quantity = (capital * risk%) / risk-per-share."""
    stop_distance = atr * STOP_ATR_MULTIPLIER if atr else entry_price * 0.03
    stop_price = entry_price - stop_distance
    risk_per_share = entry_price - stop_price
    qty = int(PAPER_CAPITAL * (RISK_PCT / 100) / risk_per_share) if risk_per_share > 0 else 0
    return round(stop_price, 2), qty


@dataclass
class RuleSignal:
    symbol: str
    signal_date: object
    last_close: float
    atr: float | None
    strategy_decision: str
    regime: str
    regime_ok: bool
    actionable: bool
    note: str


def scan(symbols: list[str], strategy_factory, now: datetime | None = None) -> tuple[str, list, dict]:
    """Evaluates the rule on the last COMPLETED daily bar for each symbol.
    Returns (nifty_regime, [RuleSignal], {symbol: error})."""
    now = now or now_ist()
    end = now.replace(tzinfo=None) + timedelta(days=1)
    start = end - timedelta(days=420)

    nifty = _nifty_series(start, end)
    if nifty and nifty[-1][0] == now.date() and now.time() < MARKET_CLOSE_IST:
        nifty = nifty[:-1]
    regime = _regime_at([c for _, c in nifty])
    regime_value = regime.regime.value
    regime_ok = regime_value in ALLOWED_REGIMES

    loader, fe = YFinanceLoader(), FeatureEngine()
    signals, errors = [], {}
    for sym in symbols:
        try:
            bars = completed_bars(loader.get_historical_bars(sym, start, end), now)
            if len(bars) < 25:
                errors[sym] = "not enough data"
                continue
            features = fe.compute(sym, bars)
            decision = strategy_factory().evaluate(sym, features, regime).decision
            is_buy = decision == Decision.BUY
            if is_buy and regime_ok:
                note = "Signal — can be logged as a paper trade"
            elif is_buy:
                note = f"Strategy says BUY but NIFTY regime {regime_value} is not allowed — rule says skip"
            else:
                note = "No signal"
            signals.append(RuleSignal(
                symbol=sym, signal_date=_bar_date(bars[-1]), last_close=round(bars[-1].close, 2),
                atr=getattr(features, "atr", None), strategy_decision=decision.value,
                regime=regime_value, regime_ok=regime_ok, actionable=is_buy and regime_ok, note=note,
            ))
        except Exception as e:
            errors[sym] = str(e)
    return regime_value, signals, errors


def rule_exit(entry_timestamp: datetime, stop_price: float, bars: list, now: datetime | None = None):
    """Replays the backtest's exit logic over the bars since entry, so an exit is
    caught even if the app wasn't opened that day:
      - STOP_LOSS if any bar from the entry day onward traded at/below the stop
        (checked first, day by day — same order as the backtest), exit at the stop;
      - TIME_BASED at the close of the MAX_HOLDING_DAYS-th COMPLETED trading day
        after the entry day.
    Returns (reason, exit_price, exit_date) or None if the trade should stay open."""
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
            if held >= MAX_HOLDING_DAYS:
                return "TIME_BASED", round(b.close, 2), d
    return None


def rule_already_used(trades: list, symbol: str, signal_date) -> str | None:
    """Blocks a second log for the same symbol: one open position per symbol
    (as in the backtest), and no re-entry on the same signal."""
    for t in trades:
        if t.strategy_name != RULE_ID or t.symbol != symbol:
            continue
        if t.exit_price is None:
            return "an open rule position already exists for this symbol"
        if _to_ist_date(t.timestamp) >= signal_date:
            return "already traded on this signal"
    return None
