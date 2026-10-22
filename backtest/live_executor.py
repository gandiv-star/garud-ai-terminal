"""LIVE execution of PASSED rules — real orders. Does nothing unless every gate is open.

Gates (all required, checked every run):
  * brokers.upstox_live.live_orders_allowed(): TRADING_MODE CONTROLLED_LIVE/LIVE and LIVE_ORDERS_ENABLED=YES
  * LIVE_RULES: comma-separated rule_ids that have PASSED their 30-trade verdict (empty = nothing)
  * LIVE_START_DATE (YYYY-MM-DD): only paper trades entered on/after this date are traded live
  * kill switch (GARUD_KILL_SWITCH) blocks new BUYs; exits always continue
  * per-order value cap LIVE_MAX_ORDER_VALUE (qty is reduced to fit, never increased)
  * any live-limit variable that is SET but invalid blocks every new BUY (fail closed);
    unset/empty variables use the safe defaults
  * portfolio guard (backtest/live_guard.py): total capital, max open positions, max % per
    stock, monthly loss limit (daily limit optional, off by default) — BUYs only; exits never blocked
  * cash check (risk/pretrade.py, added 22 Oct 2026): the broker's available equity cash is read
    once per run; a BUY is reduced to fit it (1% buffer + charges) and blocked if cash is unknown

Per paper trade (idempotent — every step is recorded as a LIVE_* audit event):
  1. ENTRY  : MARKET BUY on the paper entry day, before the entry cutoff (never chased later)
  2. STOP   : once the BUY is FILLED — or partly filled and then cancelled/rejected, or still working
              on a later day (then it is cancelled first) — a GTT SELL-BELOW stop for the FILLED qty,
              trigger rounded UP to a valid NSE tick (execution/order_state.py, risk/pretrade.py)
  3. EXIT   : when the paper trade closes or its time exit is due today: cancel the GTT, then
              SELL at market whatever is still held (covers a GTT that triggered but did not
              fill in a gap-down). Nothing is sold if the broker shows no holding.
Every order status change is stored once (LIVE_ORDER_STATE). After the trades, open live positions
are reconciled with the broker (execution/position_recon.py); mismatches are reported, never traded.
"""
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from backtest import live_guard, paper_rule
from backtest.backtest_engine import charges_for
from execution import order_state, position_recon
from risk import pretrade
from brokers.base_broker import OrderRequest, OrderSide, OrderStatus
from brokers.upstox_live import (LiveBrokerError, LiveOrdersDisabled, UpstoxLiveBroker, live_orders_allowed,
                                 max_order_value)
from brokers.upstox_sandbox import SandboxAuthError
from database.models import AuditEvent

EV_ENTRY, EV_GTT, EV_EXIT, EV_ERROR = "LIVE_ENTRY", "LIVE_GTT", "LIVE_EXIT", "LIVE_ERROR"
EV_STATE, EV_RECON = "LIVE_ORDER_STATE", "LIVE_RECON"


@dataclass
class LiveReport:
    actions: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def live_rules() -> set:
    return {r.strip() for r in os.getenv("LIVE_RULES", "").split(",") if r.strip()} & paper_rule.RULE_IDS


def live_start_date() -> date | None:
    raw = os.getenv("LIVE_START_DATE", "").strip()
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def _events(db, event_type: str) -> dict:
    out = {}
    for ev in db.get_audit_events(event_type, limit=10000):
        p = ev.payload or {}
        if p.get("trade_id"):
            out.setdefault(p["trade_id"], p)
    return out


def _record(db, event_type: str, trade, payload: dict) -> None:
    # Must succeed: an unrecorded live order would be repeated on the next run.
    db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type=event_type,
                                   symbol=trade.symbol, payload={"trade_id": trade.internal_order_id,
                                                                 "symbol": trade.symbol, **payload}))


def _state(db, trade, order_id: str, state: str, filled: int, known: dict, report) -> None:
    """Stores an order state once per change; an impossible change (e.g. FILLED -> OPEN) is reported."""
    prev = known.get(order_id)
    if prev == state:
        return
    if not order_state.legal(prev, state):
        report.errors.append(f"{trade.symbol}: broker status went {prev} → {state} (unexpected)")
    known[order_id] = state
    _record(db, EV_STATE, trade, {"order_id": order_id, "state": state, "filled": int(filled or 0),
                                  "seq": time.time_ns()})


def held_quantity(broker, symbol: str) -> int:
    """Largest quantity of `symbol` the broker reports in positions or holdings."""
    best = 0
    for fetch in (broker.get_positions, broker.get_holdings):
        body = fetch()
        rows = body.get("data") if isinstance(body, dict) else body
        for row in rows or []:
            sym = row.get("tradingsymbol") or row.get("trading_symbol")
            if sym == symbol:
                best = max(best, int(row.get("quantity") or 0))
    return best


def live_quantity(paper_qty: int, price: float) -> int:
    return max(0, min(int(paper_qty), int(max_order_value() // price))) if price > 0 else 0


def effective_status() -> dict:
    """What the live path would do right now — for the PIPELINE_RUN heartbeat and the app.
    Only switch states and numeric limits; never a token or secret."""
    ok, why = live_orders_allowed()
    try:
        cfg, problems = live_guard.GuardConfig.from_env(), live_guard.config_problems()
    except Exception as e:
        cfg, problems = live_guard.GuardConfig(), [f"live limits unreadable: {type(e).__name__}"]
    rules, start = sorted(live_rules()), live_start_date()
    if ok and not (rules and start):
        why = "LIVE_RULES/LIVE_START_DATE not set"
    return {"orders_allowed": ok, "reason": why, "rules": rules, "start_date": str(start) if start else None,
            "active": bool(ok and rules and start), "max_order_value": max_order_value(),
            "guard": cfg.as_dict(), "problems": problems,
            "set_vars": sorted(n for n in live_guard.LIMITS if os.getenv(n, "").strip())}


def live_book(trades: list, entries: dict, exits: dict) -> live_guard.Book:
    """Open live positions (value at paper entry price) and realised live P&L, scaled from
    the paper trade by live qty / paper qty."""
    by_id = {t.internal_order_id: t for t in trades}
    open_pos, realised = [], []
    for tid, e in entries.items():
        t = by_id.get(tid)
        qty = int(e.get("qty") or 0)
        if t is None or qty <= 0:
            continue
        if tid not in exits:
            open_pos.append((t.symbol, qty * t.entry_price))
        elif str(exits[tid].get("note", "")).startswith("entry"):
            continue                       # the live BUY was rejected/cancelled: no money involved
        elif t.realized_pnl is not None and t.exit_timestamp is not None and t.quantity:
            realised.append((paper_rule._to_ist_date(t.exit_timestamp), t.realized_pnl * qty / t.quantity))
    return live_guard.Book(open_pos, realised)


def execute(db, trades: list, due_exits: list | None = None, allow_entries: bool = True,
            broker=None, now: datetime | None = None) -> LiveReport:
    report = LiveReport()
    ok, why = live_orders_allowed()
    rules, start = live_rules(), live_start_date()
    if not ok or not rules or start is None:
        report.notes.append(f"Live trading OFF ({why if not ok else 'LIVE_RULES/LIVE_START_DATE not set'})")
        return report
    broker = broker or UpstoxLiveBroker()
    now = now or paper_rule.now_ist()
    due = set(due_exits or [])
    entries, gtts, exits = _events(db, EV_ENTRY), _events(db, EV_GTT), _events(db, EV_EXIT)
    try:
        guard = live_guard.GuardConfig.from_env()
        problems = live_guard.config_problems()
    except Exception as e:                 # never let a bad setting stop exits
        guard, problems = live_guard.GuardConfig(), [f"live limits unreadable: {type(e).__name__}"]
    if problems:
        # Fail closed: a limit that is set but invalid could mean more money at risk than intended.
        report.notes.append("🛡 New live BUYs blocked until fixed: " + "; ".join(problems))

    cash = {"available": None, "read": False}
    known = order_state.last_states([ev.payload or {} for ev in db.get_audit_events(EV_STATE, limit=10000)])
    for t in trades:
        if t.strategy_name not in rules or paper_rule._to_ist_date(t.timestamp) < start:
            continue
        tid = t.internal_order_id
        try:
            # 1. ENTRY
            if tid not in entries and t.exit_price is None and tid not in due:
                if not allow_entries or problems:
                    continue
                if paper_rule._to_ist_date(t.timestamp) != now.date() or not (
                        paper_rule.MARKET_OPEN_IST <= now.time() < paper_rule.ENTRY_CUTOFF_IST):
                    continue  # never chase an entry after its day / cutoff
                qty = live_quantity(t.quantity, t.entry_price)
                if qty <= 0:
                    report.errors.append(f"{t.symbol}: live qty 0 under LIVE_MAX_ORDER_VALUE")
                    continue
                qty, why = live_guard.allowed_qty(guard, live_book(trades, entries, exits), t.symbol,
                                                  t.entry_price, qty, now.date())
                if why:
                    report.notes.append(f"🛡 {t.symbol}: {why}")
                if qty <= 0:
                    continue
                if cash["available"] is None and not cash["read"]:
                    cash["read"] = True
                    try:
                        cash["available"] = pretrade.available_margin(broker.get_funds())
                    except Exception as e:
                        report.notes.append(f"💰 funds unreadable ({type(e).__name__}) — new BUYs blocked this run")
                cm = charges_for(now.date())
                qty, why = pretrade.affordable_qty(qty, t.entry_price, cash["available"], cm.buy_charges)
                if why:
                    report.notes.append(f"💰 {t.symbol}: {why}")
                bad = pretrade.quantity_problem(qty)
                if qty <= 0 or bad:
                    continue
                res = broker.place_order(OrderRequest(f"{tid}:LIVE_ENTRY", t.symbol, "NSE", OrderSide.BUY, qty,
                                                      "MARKET", price=t.entry_price, product_type="D"))
                if not res.broker_order_id:
                    raise LiveBrokerError(f"BUY rejected: {str(res.raw_response)[:200]}")
                _record(db, EV_ENTRY, t, {"order_id": res.broker_order_id, "qty": qty})
                entries[tid] = {"order_id": res.broker_order_id, "qty": qty, "symbol": t.symbol}
                cash["available"] -= qty * t.entry_price + cm.buy_charges(qty * t.entry_price)
                report.actions.append(f"LIVE BUY {t.symbol} x{qty} #{res.broker_order_id}")
                continue  # fill is checked on the next run

            if tid not in entries or tid in exits:
                continue
            entry = entries[tid]

            # 3. EXIT (checked before placing a stop, so a due exit never gets a fresh GTT)
            if t.exit_price is not None or tid in due:
                if tid in gtts:
                    try:
                        broker.cancel_gtt(gtts[tid]["gtt_id"])
                    except LiveBrokerError:
                        pass  # already triggered/cancelled — the holding check below decides
                never_filled = None
                if tid not in gtts:
                    # No stop was placed, so the BUY may never have filled: cancel it if still
                    # pending (no orphan position later) and remember if nothing was bought.
                    try:
                        st = broker.get_order_status(entry["order_id"])
                        if st.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                            try:
                                broker.cancel_order(entry["order_id"])
                            except Exception:
                                pass
                        if st.status in (OrderStatus.REJECTED, OrderStatus.CANCELLED) or not st.filled_quantity:
                            never_filled = st.status.value
                    except Exception:
                        pass               # unknown — the holding check below still decides
                held = min(held_quantity(broker, t.symbol), int(entry["qty"]))
                order_id = None
                if held > 0:
                    price = t.exit_price or t.entry_price
                    res = broker.place_order(OrderRequest(f"{tid}:LIVE_EXIT", t.symbol, "NSE", OrderSide.SELL,
                                                          held, "MARKET", price=price, product_type="D"))
                    if not res.broker_order_id:
                        raise LiveBrokerError(f"SELL rejected: {str(res.raw_response)[:200]}")
                    order_id = res.broker_order_id
                exit_payload = {"order_id": order_id, "qty": held}
                if held == 0 and never_filled:
                    exit_payload["note"] = f"entry {never_filled} — nothing bought"
                _record(db, EV_EXIT, t, exit_payload)
                exits[tid] = exit_payload
                report.actions.append(f"LIVE SELL {t.symbol} x{held}" + (f" #{order_id}" if order_id else " (nothing held)"))
                continue

            # 2. STOP at the broker once shares are bought (order state machine)
            if tid not in gtts:
                try:
                    st = broker.get_order_status(entry["order_id"])
                except (LiveOrdersDisabled, SandboxAuthError):
                    raise
                except Exception as e:
                    _state(db, t, entry["order_id"], order_state.UNKNOWN, 0, known, report)
                    report.notes.append(f"❓ {t.symbol}: order status unknown ({type(e).__name__}) — retry next run")
                    continue
                status = getattr(st.status, "value", st.status)
                _state(db, t, entry["order_id"], status, st.filled_quantity, known, report)
                action, q = order_state.entry_action(status, st.filled_quantity,
                                                     paper_rule._to_ist_date(t.timestamp), now.date())
                if action == "cancel_and_protect":
                    try:
                        broker.cancel_order(entry["order_id"])
                        report.notes.append(f"⏹ {t.symbol}: live BUY still {status} on a later day — cancelled")
                    except Exception as e:
                        report.errors.append(f"{t.symbol}: cancel of stale BUY failed: {e}")
                        continue
                if action in ("protect", "cancel_and_protect") and q > 0:
                    trigger = pretrade.round_to_tick(t.stop_price, "up")
                    gtt_id = broker.place_gtt_stop(t.symbol, q, trigger)
                    _record(db, EV_GTT, t, {"gtt_id": gtt_id, "qty": q, "stop": trigger})
                    gtts[tid] = {"gtt_id": gtt_id, "qty": q}
                    report.actions.append(f"LIVE STOP {t.symbol} x{q} @ {trigger} ({gtt_id})"
                                          + ("" if q == int(entry.get("qty") or 0) else f" — partial fill {q}/{entry.get('qty')}"))
                elif action in ("none", "cancel_and_protect"):
                    _record(db, EV_EXIT, t, {"order_id": None, "qty": 0, "note": f"entry {status}"})
                    exits[tid] = {"qty": 0}
                    report.errors.append(f"{t.symbol}: live BUY {status} — no position")
        except (LiveOrdersDisabled, SandboxAuthError, LiveBrokerError) as e:
            report.errors.append(f"{t.symbol}: {e}")
            if isinstance(e, SandboxAuthError) or "static IP" in str(e):
                report.notes.append("🔑 Live token/static IP problem — live trading paused this run")
                break
        except Exception as e:  # never let one trade stop the others; surfaced on Telegram
            report.errors.append(f"{t.symbol}: unexpected {type(e).__name__}: {str(e)[:200]}")
    _reconcile(db, broker, entries, gtts, exits, report, now)
    return report


def _reconcile(db, broker, entries: dict, gtts: dict, exits: dict, report, now) -> None:
    expect = position_recon.expected(entries, gtts, exits)
    if not expect:
        return
    try:
        held = position_recon.broker_quantities(broker)
    except Exception as e:
        report.notes.append(f"🔎 reconciliation skipped: broker positions unreadable ({type(e).__name__})")
        return
    problems = position_recon.reconcile(expect, held)
    for p in problems:
        report.errors.append(f"🔎 {p}")
    try:
        db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type=EV_RECON, symbol=None,
                                       payload={"day": str(now.date()), "checked": len(expect), "problems": problems}))
    except Exception:
        pass
