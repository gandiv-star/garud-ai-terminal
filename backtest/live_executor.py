"""LIVE execution of PASSED rules — real orders. Does nothing unless every gate is open.

Gates (all required, checked every run):
  * brokers.upstox_live.live_orders_allowed(): TRADING_MODE CONTROLLED_LIVE/LIVE and LIVE_ORDERS_ENABLED=YES
  * LIVE_RULES: comma-separated rule_ids that have PASSED their 30-trade verdict (empty = nothing)
  * LIVE_START_DATE (YYYY-MM-DD): only paper trades entered on/after this date are traded live
  * kill switch (GARUD_KILL_SWITCH) blocks new BUYs; exits always continue
  * per-order value cap LIVE_MAX_ORDER_VALUE (qty is reduced to fit, never increased)

Per paper trade (idempotent — every step is recorded as a LIVE_* audit event):
  1. ENTRY  : MARKET BUY on the paper entry day, before the entry cutoff (never chased later)
  2. STOP   : once the BUY is FILLED, a GTT SELL-BELOW stop at the paper stop for the filled qty
  3. EXIT   : when the paper trade closes or its time exit is due today: cancel the GTT, then
              SELL at market whatever is still held (covers a GTT that triggered but did not
              fill in a gap-down). Nothing is sold if the broker shows no holding.
"""
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from backtest import paper_rule
from brokers.base_broker import OrderRequest, OrderSide, OrderStatus
from brokers.upstox_live import LiveBrokerError, LiveOrdersDisabled, UpstoxLiveBroker, live_orders_allowed, max_order_value
from brokers.upstox_sandbox import SandboxAuthError
from database.models import AuditEvent

EV_ENTRY, EV_GTT, EV_EXIT, EV_ERROR = "LIVE_ENTRY", "LIVE_GTT", "LIVE_EXIT", "LIVE_ERROR"


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
                                   symbol=trade.symbol, payload={"trade_id": trade.internal_order_id, **payload}))


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

    for t in trades:
        if t.strategy_name not in rules or paper_rule._to_ist_date(t.timestamp) < start:
            continue
        tid = t.internal_order_id
        try:
            # 1. ENTRY
            if tid not in entries and t.exit_price is None and tid not in due:
                if not allow_entries:
                    continue
                if paper_rule._to_ist_date(t.timestamp) != now.date() or not (
                        paper_rule.MARKET_OPEN_IST <= now.time() < paper_rule.ENTRY_CUTOFF_IST):
                    continue  # never chase an entry after its day / cutoff
                qty = live_quantity(t.quantity, t.entry_price)
                if qty <= 0:
                    report.errors.append(f"{t.symbol}: live qty 0 under LIVE_MAX_ORDER_VALUE")
                    continue
                res = broker.place_order(OrderRequest(f"{tid}:LIVE_ENTRY", t.symbol, "NSE", OrderSide.BUY, qty,
                                                      "MARKET", price=t.entry_price, product_type="D"))
                if not res.broker_order_id:
                    raise LiveBrokerError(f"BUY rejected: {str(res.raw_response)[:200]}")
                _record(db, EV_ENTRY, t, {"order_id": res.broker_order_id, "qty": qty})
                entries[tid] = {"order_id": res.broker_order_id, "qty": qty}
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
                held = min(held_quantity(broker, t.symbol), int(entry["qty"]))
                order_id = None
                if held > 0:
                    price = t.exit_price or t.entry_price
                    res = broker.place_order(OrderRequest(f"{tid}:LIVE_EXIT", t.symbol, "NSE", OrderSide.SELL,
                                                          held, "MARKET", price=price, product_type="D"))
                    if not res.broker_order_id:
                        raise LiveBrokerError(f"SELL rejected: {str(res.raw_response)[:200]}")
                    order_id = res.broker_order_id
                _record(db, EV_EXIT, t, {"order_id": order_id, "qty": held})
                report.actions.append(f"LIVE SELL {t.symbol} x{held}" + (f" #{order_id}" if order_id else " (nothing held)"))
                continue

            # 2. STOP at the broker once the BUY is filled
            if tid not in gtts:
                st = broker.get_order_status(entry["order_id"])
                if st.status == OrderStatus.FILLED and st.filled_quantity > 0:
                    gtt_id = broker.place_gtt_stop(t.symbol, st.filled_quantity, t.stop_price)
                    _record(db, EV_GTT, t, {"gtt_id": gtt_id, "qty": st.filled_quantity, "stop": t.stop_price})
                    gtts[tid] = {"gtt_id": gtt_id}
                    report.actions.append(f"LIVE STOP {t.symbol} x{st.filled_quantity} @ {t.stop_price} ({gtt_id})")
                elif st.status in (OrderStatus.REJECTED, OrderStatus.CANCELLED):
                    _record(db, EV_EXIT, t, {"order_id": None, "qty": 0, "note": f"entry {st.status.value}"})
                    report.errors.append(f"{t.symbol}: live BUY {st.status.value} — no position")
        except (LiveOrdersDisabled, SandboxAuthError, LiveBrokerError) as e:
            report.errors.append(f"{t.symbol}: {e}")
            if isinstance(e, SandboxAuthError) or "static IP" in str(e):
                report.notes.append("🔑 Live token/static IP problem — live trading paused this run")
                break
        except Exception as e:  # never let one trade stop the others; surfaced on Telegram
            report.errors.append(f"{t.symbol}: unexpected {type(e).__name__}: {str(e)[:200]}")
    return report
