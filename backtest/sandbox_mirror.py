"""Mirrors every automatic rule trade (entry BUY, exit SELL) into the Upstox SANDBOX.

Purpose: exercise the complete live-order path — symbol -> instrument key, order
payload, duplicate protection (OrderManager), error handling and reconciliation —
with zero money and no static IP, so going live later is only a broker switch.

Idempotent: a mirrored order is recorded as a SANDBOX_ORDER audit event keyed by
"<trade id>:ENTRY" / "<trade id>:EXIT"; anything not yet recorded is (re)tried on
the next run. Mirroring never changes the paper-trading records themselves.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backtest import paper_rule
from brokers.base_broker import OrderRequest, OrderSide
from brokers.upstox_sandbox import SandboxAuthError, UpstoxSandboxBroker
from database.models import AuditEvent
from execution.order_manager import DuplicateOrderError, OrderManager
from execution.reconciliation import ReconciliationEngine

EVENT_OK = "SANDBOX_ORDER"
EVENT_FAIL = "SANDBOX_ORDER_FAILED"


@dataclass
class MirrorReport:
    placed: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    unreconciled: list = field(default_factory=list)


def expected_orders(trades: list, due_exits: set | frozenset = frozenset()) -> list[dict]:
    """Every rule trade implies a BUY at entry and a SELL at exit — the exit SELL is
    sent before the close when a time exit is due today, otherwise once the trade is closed."""
    out = []
    for t in trades:
        if t.strategy_name not in paper_rule.RULE_IDS:
            continue
        out.append({"internal_order_id": f"{t.internal_order_id}:ENTRY", "symbol": t.symbol,
                    "side": "BUY", "quantity": t.quantity})
        if t.exit_price is not None or t.internal_order_id in due_exits:
            out.append({"internal_order_id": f"{t.internal_order_id}:EXIT", "symbol": t.symbol,
                        "side": "SELL", "quantity": t.quantity})
    return out


def mirrored_orders(db) -> list[dict]:
    rows = {}
    for ev in db.get_audit_events(EVENT_OK, limit=10000):
        p = ev.payload or {}
        if p.get("internal_order_id"):
            rows.setdefault(p["internal_order_id"], p)
    return list(rows.values())


def mirror(db, trades: list, broker: UpstoxSandboxBroker | None = None, now: datetime | None = None,
           due_exits: list | None = None, allow_entries: bool = True) -> MirrorReport:
    report = MirrorReport()
    broker = broker or UpstoxSandboxBroker()
    if not broker.token:
        report.notes.append("Sandbox mirror off (UPSTOX_SANDBOX_TOKEN not set)")
        return report
    now = now or paper_rule.now_ist()
    broker.after_hours = not (paper_rule.MARKET_OPEN_IST <= now.time() < paper_rule.MARKET_CLOSE_IST)

    expected = expected_orders(trades, frozenset(due_exits or []))
    done = {o["internal_order_id"] for o in mirrored_orders(db)}
    manager = OrderManager(broker=broker, dedup_window_seconds=0)

    for o in expected:
        if o["internal_order_id"] in done:
            continue
        if o["side"] == "BUY" and not allow_entries:
            continue  # kill switch: never open new broker positions; exits still go through
        req = OrderRequest(internal_order_id=o["internal_order_id"], symbol=o["symbol"], exchange="NSE",
                           side=OrderSide(o["side"]), quantity=o["quantity"], order_type="MARKET",
                           product_type="D")
        try:
            result = manager.submit(req)
        except SandboxAuthError as e:
            report.failed.append(f"{o['symbol']} {o['side']}: {e}")
            report.notes.append("🔑 Upstox sandbox token needs renewing (valid 30 days) — mirroring paused")
            break
        except DuplicateOrderError:
            continue
        except Exception as e:
            _save(db, EVENT_FAIL, o, {"error": str(e)[:300]})
            report.failed.append(f"{o['symbol']} {o['side']}: {str(e)[:150]}")
            continue
        if result.broker_order_id:
            # Must be recorded, otherwise the next run would place it again: no try/except here.
            _save(db, EVENT_OK, o, {"broker_order_id": result.broker_order_id, "status": result.status.value,
                                    "amo": broker.after_hours}, strict=True)
            done.add(o["internal_order_id"])
            report.placed.append(f"{o['symbol']} {o['side']} x{o['quantity']} → sandbox #{result.broker_order_id}")
        else:
            _save(db, EVENT_FAIL, o, {"response": result.raw_response})
            report.failed.append(f"{o['symbol']} {o['side']}: rejected {str(result.raw_response)[:200]}")

    recon = ReconciliationEngine().reconcile(
        [{k: o[k] for k in ("internal_order_id", "side", "quantity")} for o in expected],
        [{"internal_order_id": m["internal_order_id"], "side": m.get("side"), "quantity": m.get("quantity")}
         for m in mirrored_orders(db)],
    )
    report.unreconciled = (
        [f"not mirrored: {i}" for i in recon.missing_from_broker]
        + [f"unknown sandbox order: {i}" for i in recon.missing_from_internal]
        + [f"{m.internal_order_id} {m.field}: ours {m.internal_value} vs sandbox {m.broker_value}"
           for m in recon.mismatches]
    )
    return report


def _save(db, event_type: str, order: dict, extra: dict, strict: bool = False) -> None:
    event = AuditEvent(timestamp=datetime.now(timezone.utc), event_type=event_type,
                       symbol=order["symbol"], payload={**order, **extra})
    if strict:
        db.save_audit_event(event)
        return
    try:
        db.save_audit_event(event)
    except Exception:
        pass
