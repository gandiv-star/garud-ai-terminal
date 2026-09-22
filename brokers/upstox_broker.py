import requests

from brokers.base_broker import BaseBroker, OrderRequest, OrderResult
from security.secrets_manager import SecretsManager

BASE_URL = "https://api.upstox.com/v2"


class UpstoxBroker(BaseBroker):
    """
    Read-only for now (funds/positions/holdings). Order placement is
    deliberately NOT implemented yet — that's the highest-risk piece and
    needs its own careful, separately-tested pass.

    Access token must be refreshed daily via Upstox's own interactive OAuth
    login (outside this codebase) — Upstox does not support automated
    login. Some Upstox portfolio/funds endpoints may require a registered
    static IP; GitHub Actions runners have a changing IP, so a 401/403
    here could mean either an expired token OR an IP-whitelist mismatch.
    """

    def __init__(self, access_token: str | None = None):
        self.access_token = access_token or SecretsManager.get("BROKER_ACCESS_TOKEN")

    def _headers(self) -> dict:
        return {"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"}

    def authenticate(self) -> None:
        if not self.access_token:
            raise RuntimeError("No access token set — see BROKER_ACCESS_TOKEN.")

    def get_funds(self) -> dict:
        response = requests.get(f"{BASE_URL}/user/get-funds-and-margin", headers=self._headers())
        response.raise_for_status()
        return response.json()

    def get_positions(self) -> list[dict]:
        response = requests.get(f"{BASE_URL}/portfolio/short-term-positions", headers=self._headers())
        response.raise_for_status()
        return response.json()

    def get_holdings(self) -> list[dict]:
        response = requests.get(f"{BASE_URL}/portfolio/long-term-holdings", headers=self._headers())
        response.raise_for_status()
        return response.json()

    def place_order(self, order: OrderRequest) -> OrderResult:
        raise NotImplementedError("Order placement not yet implemented — deliberately deferred.")

    def modify_order(self, broker_order_id: str, **changes) -> OrderResult:
        raise NotImplementedError("Order modification not yet implemented.")

    def cancel_order(self, broker_order_id: str) -> OrderResult:
        raise NotImplementedError("Order cancellation not yet implemented.")

    def get_order_status(self, broker_order_id: str) -> OrderResult:
        raise NotImplementedError("Order status lookup not yet implemented.")
