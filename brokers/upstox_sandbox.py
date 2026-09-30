"""Upstox SANDBOX broker — simulated orders only, no real money, no static IP needed.

A sandbox token is issued by a separate "Sandbox app" and is valid for 30 days.
It cannot place live orders even by mistake. Upstox's sandbox supports only
place / modify / cancel, so funds, positions and order status are not available.
"""
import gzip
import io
import json
import os

import requests

from brokers.base_broker import BaseBroker, OrderRequest, OrderResult, OrderStatus

# Host verified from Upstox community usage (sandbox.upstox.com in the overview page does not resolve).
# v2 place-order is marked deprecated, so v3 is tried if v2 answers 404/410.
SANDBOX_PLACE_URLS = (
    os.getenv("UPSTOX_SANDBOX_PLACE_URL", "https://api-sandbox.upstox.com/v2/order/place"),
    "https://api-sandbox.upstox.com/v3/order/place",
)
INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
ORDER_TAG = "garud"


class SandboxAuthError(Exception):
    """Token missing, expired (30-day validity) or invalid."""


def load_nse_equity_keys(url: str = INSTRUMENTS_URL, timeout: int = 60) -> dict:
    """NSE trading symbol -> Upstox instrument_key (e.g. RELIANCE -> NSE_EQ|INE002A01018)."""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    data = json.load(gzip.GzipFile(fileobj=io.BytesIO(resp.content)))
    keys = {}
    for row in data:
        if row.get("segment") == "NSE_EQ" and row.get("instrument_type") in ("EQ", None):
            sym, key = row.get("trading_symbol"), row.get("instrument_key")
            if sym and key:
                keys.setdefault(sym, key)
    return keys


class UpstoxSandboxBroker(BaseBroker):
    PLACE_URLS = SANDBOX_PLACE_URLS
    TOKEN_ENV = "UPSTOX_SANDBOX_TOKEN"
    AUTH_HINT = "Sandbox token expired or invalid (HTTP 401) — generate a new one"

    def __init__(self, token: str | None = None, instrument_keys: dict | None = None, timeout: int = 20):
        self.token = token if token is not None else os.getenv(self.TOKEN_ENV)
        self._keys = instrument_keys
        self.timeout = timeout
        self.after_hours = False  # True -> orders go as AMO (after-market orders)

    # -- helpers -------------------------------------------------------------
    def _headers(self) -> dict:
        return {"Accept": "application/json", "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}"}

    def instrument_key(self, symbol: str) -> str:
        if self._keys is None:
            self._keys = load_nse_equity_keys()
        key = self._keys.get(symbol)
        if not key:
            raise KeyError(f"No NSE_EQ instrument key for {symbol}")
        return key

    def build_payload(self, order: OrderRequest, after_hours: bool) -> dict:
        if order.quantity <= 0:
            raise ValueError("quantity must be positive")
        if order.order_type != "MARKET":
            raise ValueError("only MARKET orders are used by the rule engine")
        return {
            "quantity": int(order.quantity),
            "product": order.product_type or "D",
            "validity": "DAY",
            "price": 0,
            "tag": ORDER_TAG,
            "instrument_token": self.instrument_key(order.symbol),
            "order_type": "MARKET",
            "transaction_type": order.side.value,
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": bool(after_hours),
        }

    def _pre_place_checks(self, order: OrderRequest) -> None:
        """Hook for subclasses (the live broker adds its safety gates here)."""

    # -- BaseBroker ----------------------------------------------------------
    def authenticate(self) -> None:
        if not self.token:
            raise SandboxAuthError(f"{self.TOKEN_ENV} is not set")

    def place_order(self, order: OrderRequest) -> OrderResult:
        self.authenticate()
        self._pre_place_checks(order)
        payload = self.build_payload(order, self.after_hours)
        for url in self.PLACE_URLS:
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
            if resp.status_code not in (404, 410):
                break
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text[:500]}
        if resp.status_code == 401:
            raise SandboxAuthError(self.AUTH_HINT)
        data = (body.get("data") or {}) if isinstance(body, dict) else {}
        order_id = data.get("order_id") or ((data.get("order_ids") or [None])[0])
        if resp.ok and body.get("status") == "success" and order_id:
            return OrderResult(order.internal_order_id, order_id, OrderStatus.OPEN, raw_response=body)
        return OrderResult(order.internal_order_id, None, OrderStatus.REJECTED,
                           raw_response={"http": resp.status_code, "body": body})

    def get_funds(self) -> dict:
        raise NotImplementedError("Upstox sandbox does not provide funds")

    def get_positions(self) -> list[dict]:
        raise NotImplementedError("Upstox sandbox does not provide positions")

    def get_holdings(self) -> list[dict]:
        raise NotImplementedError("Upstox sandbox does not provide holdings")

    def modify_order(self, broker_order_id: str, **changes) -> OrderResult:
        raise NotImplementedError("Not used by the rule engine")

    def cancel_order(self, broker_order_id: str) -> OrderResult:
        raise NotImplementedError("Not used by the rule engine")

    def get_order_status(self, broker_order_id: str) -> OrderResult:
        raise NotImplementedError("Upstox sandbox does not provide order status")
