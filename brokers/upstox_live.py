"""Upstox LIVE broker — REAL orders with REAL money. Switched OFF by default.

Nothing here can send an order unless ALL of these hold at call time:
  1. TRADING_MODE is CONTROLLED_LIVE or LIVE
  2. LIVE_ORDERS_ENABLED == "YES"
  3. the order value (qty x reference price) is within LIVE_MAX_ORDER_VALUE (default Rs.25,000)
The gates are checked before any network call.

Live requirements that no code can remove (SEBI / Upstox):
  * a static IP registered with Upstox (API orders from a changing IP are refused);
  * a daily access token from Upstox's own login (BROKER_ACCESS_TOKEN);
  * one-time EDIS authorisation on Upstox Pro before GTT SELL orders on delivery holdings.

Stop-loss is kept AT THE BROKER as a single-leg GTT: SELL when price goes BELOW the
stop (valid up to 1 year). Upstox executes a triggered GTT as a LIMIT order at the
trigger price, so in a gap-down below the stop it may not fill — the automatic run
must then close the position at market (handled by the exit logic, not here).
"""
import os

import requests

from brokers.base_broker import OrderRequest, OrderResult, OrderSide, OrderStatus
from brokers.upstox_sandbox import UpstoxSandboxBroker

LIVE_PLACE_URLS = ("https://api-hft.upstox.com/v3/order/place",)
CANCEL_URL = "https://api-hft.upstox.com/v3/order/cancel"
ORDER_DETAILS_URL = "https://api.upstox.com/v2/order/details"
GTT_PLACE_URL = "https://api.upstox.com/v3/order/gtt/place"
GTT_CANCEL_URL = "https://api.upstox.com/v3/order/gtt/cancel"
POSITIONS_URL = "https://api.upstox.com/v2/portfolio/short-term-positions"
HOLDINGS_URL = "https://api.upstox.com/v2/portfolio/long-term-holdings"
LIVE_MODES = ("CONTROLLED_LIVE", "LIVE")
DEFAULT_MAX_ORDER_VALUE = 25000.0

_STATUS_MAP = {
    "complete": OrderStatus.FILLED,
    "rejected": OrderStatus.REJECTED,
    "cancelled": OrderStatus.CANCELLED,
    "open": OrderStatus.OPEN,
    "trigger pending": OrderStatus.OPEN,
    "after market order req received": OrderStatus.OPEN,
}


class LiveOrdersDisabled(Exception):
    """Raised before any network call when a live-order safety gate is closed."""


class LiveBrokerError(Exception):
    """Broker refused the request (auth, static IP, validation...)."""


def live_orders_allowed() -> tuple[bool, str]:
    mode = os.getenv("TRADING_MODE", "").strip().upper()
    if mode not in LIVE_MODES:
        return False, f"TRADING_MODE is {mode or 'unset'} (needs CONTROLLED_LIVE or LIVE)"
    if os.getenv("LIVE_ORDERS_ENABLED", "").strip().upper() != "YES":
        return False, "LIVE_ORDERS_ENABLED is not YES"
    return True, "live orders enabled"


def max_order_value() -> float:
    try:
        return float(os.getenv("LIVE_MAX_ORDER_VALUE", DEFAULT_MAX_ORDER_VALUE))
    except ValueError:
        return DEFAULT_MAX_ORDER_VALUE


class UpstoxLiveBroker(UpstoxSandboxBroker):
    PLACE_URLS = LIVE_PLACE_URLS
    TOKEN_ENV = "BROKER_ACCESS_TOKEN"
    AUTH_HINT = ("Live token expired/invalid or request not from the registered static IP (HTTP 401) — "
                 "refresh BROKER_ACCESS_TOKEN via Upstox login and check the static IP")

    # -- safety gates ----------------------------------------------------------
    def _gate(self) -> None:
        ok, why = live_orders_allowed()
        if not ok:
            raise LiveOrdersDisabled(why)
        self.authenticate()

    def _pre_place_checks(self, order: OrderRequest) -> None:
        self._gate()
        if order.side == OrderSide.SELL:
            return  # exits reduce risk: never blocked by the value cap
        if not order.price or order.price <= 0:
            raise LiveOrdersDisabled("reference price (OrderRequest.price) is required for the value cap")
        value = order.quantity * order.price
        if value > max_order_value():
            raise LiveOrdersDisabled(f"order value Rs.{value:,.0f} exceeds LIVE_MAX_ORDER_VALUE "
                                     f"Rs.{max_order_value():,.0f}")

    def _check(self, resp) -> dict:
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text[:500]}
        if resp.status_code == 401:
            raise LiveBrokerError(self.AUTH_HINT)
        if not resp.ok or (isinstance(body, dict) and body.get("status") != "success"):
            raise LiveBrokerError(f"HTTP {resp.status_code}: {str(body)[:300]}")
        return body

    # -- portfolio (read-only; needs the registered static IP) ----------------------
    def get_positions(self) -> dict:
        self.authenticate()
        return self._check(requests.get(POSITIONS_URL, headers=self._headers(), timeout=self.timeout))

    def get_holdings(self) -> dict:
        self.authenticate()
        return self._check(requests.get(HOLDINGS_URL, headers=self._headers(), timeout=self.timeout))

    # -- orders ------------------------------------------------------------------
    def get_order_status(self, broker_order_id: str) -> OrderResult:
        self.authenticate()
        resp = requests.get(ORDER_DETAILS_URL, headers=self._headers(),
                            params={"order_id": broker_order_id}, timeout=self.timeout)
        data = self._check(resp).get("data") or {}
        status = _STATUS_MAP.get(str(data.get("status", "")).lower(), OrderStatus.PENDING)
        return OrderResult(internal_order_id=data.get("tag") or "", broker_order_id=broker_order_id,
                           status=status, filled_quantity=int(data.get("filled_quantity") or 0),
                           average_price=data.get("average_price"), raw_response=data)

    def cancel_order(self, broker_order_id: str) -> OrderResult:
        self._gate()
        resp = requests.delete(CANCEL_URL, headers=self._headers(),
                               params={"order_id": broker_order_id}, timeout=self.timeout)
        self._check(resp)
        return OrderResult(internal_order_id="", broker_order_id=broker_order_id, status=OrderStatus.CANCELLED)

    # -- broker-side stop-loss (GTT) ----------------------------------------------
    def build_gtt_stop_payload(self, symbol: str, quantity: int, stop_price: float) -> dict:
        if quantity <= 0 or stop_price <= 0:
            raise ValueError("quantity and stop_price must be positive")
        return {
            "type": "SINGLE",
            "quantity": int(quantity),
            "product": "D",
            "instrument_token": self.instrument_key(symbol),
            "transaction_type": "SELL",
            "rules": [{"strategy": "ENTRY", "trigger_type": "BELOW", "trigger_price": round(float(stop_price), 2)}],
        }

    def place_gtt_stop(self, symbol: str, quantity: int, stop_price: float) -> str:
        self._gate()
        payload = self.build_gtt_stop_payload(symbol, quantity, stop_price)
        resp = requests.post(GTT_PLACE_URL, headers=self._headers(), json=payload, timeout=self.timeout)
        ids = (self._check(resp).get("data") or {}).get("gtt_order_ids") or []
        if not ids:
            raise LiveBrokerError("GTT placed but no gtt_order_id returned")
        return ids[0]

    def cancel_gtt(self, gtt_order_id: str) -> None:
        self._gate()
        resp = requests.delete(GTT_CANCEL_URL, headers=self._headers(),
                               json={"gtt_order_id": gtt_order_id}, timeout=self.timeout)
        self._check(resp)
