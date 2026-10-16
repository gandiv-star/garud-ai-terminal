"""Portfolio-level safety limits for LIVE orders (paper rules are never affected).

Every new live BUY is checked against the money actually at work, so real trading can
never use more capital than exists, pile into one stock, or keep buying after losses.

Limits (GitHub variables; safe defaults used when unset or invalid):
  LIVE_CAPITAL              total money for live trading          default Rs.1,00,000
  LIVE_MAX_OPEN             max open live positions                default 5
  LIVE_MAX_STOCK_PCT        max % of capital in one stock          default 20
  LIVE_DAILY_LOSS_LIMIT     stop new BUYs after this realised loss today        default OFF (0)
  LIVE_MONTHLY_LOSS_LIMIT   stop new BUYs after this realised loss this month   default Rs.6,000
A BUY that doesn't fit is reduced to fit; if not even 1 share fits it is skipped.
Exits are never blocked.
"""
import math
import os
from dataclasses import dataclass
from datetime import date


def _num(name: str, default: float, minimum: float = 0.0, maximum: float = 1e9) -> float:
    """A finite number in (minimum, maximum]; anything else (text, inf, nan, <= minimum) -> default."""
    try:
        v = float(os.getenv(name, "").strip() or default)
    except (ValueError, TypeError, OverflowError):
        return default
    return v if math.isfinite(v) and minimum < v <= maximum else default


@dataclass(frozen=True)
class GuardConfig:
    capital: float = 100000.0
    max_open: int = 5
    max_stock_pct: float = 20.0
    daily_loss_limit: float = 0.0          # 0 = off (decided 16 Oct 2026: don't miss same-day chances)
    monthly_loss_limit: float = 6000.0

    @classmethod
    def from_env(cls) -> "GuardConfig":
        d = cls()
        return cls(capital=_num("LIVE_CAPITAL", d.capital),
                   max_open=max(1, int(_num("LIVE_MAX_OPEN", d.max_open, maximum=1000))),
                   max_stock_pct=min(_num("LIVE_MAX_STOCK_PCT", d.max_stock_pct), 100.0),
                   daily_loss_limit=_num("LIVE_DAILY_LOSS_LIMIT", d.daily_loss_limit),
                   monthly_loss_limit=_num("LIVE_MONTHLY_LOSS_LIMIT", d.monthly_loss_limit))


@dataclass
class Book:
    """Live state at the moment of a decision."""
    open_positions: list      # [(symbol, value_at_entry)]
    realised: list            # [(exit_date, pnl)]


def allowed_qty(cfg: GuardConfig, book: Book, symbol: str, price: float, qty: int, today: date) -> tuple[int, str]:
    """(quantity allowed, reason). reason is '' when the full quantity is allowed."""
    if qty <= 0 or price <= 0:
        return 0, "nothing to buy"
    day_pnl = sum(p for d, p in book.realised if d == today)
    month_pnl = sum(p for d, p in book.realised if (d.year, d.month) == (today.year, today.month))
    if cfg.daily_loss_limit > 0 and day_pnl <= -cfg.daily_loss_limit:
        return 0, f"daily loss limit hit (Rs.{day_pnl:,.0f})"
    if cfg.monthly_loss_limit > 0 and month_pnl <= -cfg.monthly_loss_limit:
        return 0, f"monthly loss limit hit (Rs.{month_pnl:,.0f})"
    if len(book.open_positions) >= cfg.max_open:
        return 0, f"max {cfg.max_open} open positions"
    used = sum(v for _, v in book.open_positions)
    in_stock = sum(v for s, v in book.open_positions if s == symbol)
    room = min(cfg.capital - used, cfg.capital * cfg.max_stock_pct / 100 - in_stock)
    fit = int(max(room, 0) // price)
    if fit <= 0:
        why = ("capital fully used" if cfg.capital - used < price
               else f"{symbol} already at {cfg.max_stock_pct:.0f}% of capital")
        return 0, why
    if fit < qty:
        return fit, f"reduced {qty}→{fit} to stay within capital/stock limits"
    return qty, ""


def simulate(trades: list, cfg: GuardConfig, rule_ids: set | None = None) -> dict:
    """Replays closed+open paper trades in entry order as if traded live with the guard.
    trades: dicts with rule, symbol, entry, qty, entry_date, exit_date, pnl (pnl None if open).
    Returns counts and P&L with vs without the guard."""
    rows = sorted([t for t in trades if rule_ids is None or t["rule"] in rule_ids],
                  key=lambda t: (t["entry_date"], t["symbol"]))
    taken, reduced, skipped, reasons = 0, 0, 0, {}
    open_pos, realised = [], []          # open_pos: (symbol, value, exit_date or None)
    pnl_guard = pnl_all = 0.0
    for t in rows:
        d = t["entry_date"]
        # close positions whose exit happened before this entry day
        still = []
        for sym, val, ex, pnl in open_pos:
            if ex is not None and ex < d:
                realised.append((ex, pnl))
            else:
                still.append((sym, val, ex, pnl))
        open_pos = still
        q, why = allowed_qty(cfg, Book([(s, v) for s, v, _, _ in open_pos], realised),
                             t["symbol"], t["entry"], t["qty"], d)
        if t["pnl"] is not None:
            pnl_all += t["pnl"]
        if q <= 0:
            skipped += 1
            reasons[why.split(" (")[0]] = reasons.get(why.split(" (")[0], 0) + 1
            continue
        taken += 1
        if q < t["qty"]:
            reduced += 1
        scaled = t["pnl"] * q / t["qty"] if t["pnl"] is not None else None
        if scaled is not None:
            pnl_guard += scaled
        open_pos.append((t["symbol"], q * t["entry"], t["exit_date"], scaled or 0.0))
    open_now = sum(v for _, v, ex, _ in open_pos if ex is None)
    return {"trades": len(rows), "taken": taken, "reduced": reduced, "skipped": skipped,
            "reasons": reasons, "pnl_with_guard": round(pnl_guard, 2), "pnl_without": round(pnl_all, 2),
            "open_value_now": round(open_now, 2)}
