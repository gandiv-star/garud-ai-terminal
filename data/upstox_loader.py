from datetime import datetime

import requests

from data.data_loader import Bar, DataLoader
from security.secrets_manager import SecretsManager

UPSTOX_LTP_URL = "https://api.upstox.com/v3/market-quote/ltp"


class UpstoxLoader(DataLoader):
    def __init__(self, access_token: str | None = None):
        self.access_token = access_token or SecretsManager.get("BROKER_ACCESS_TOKEN")

    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

    def get_latest_quote_by_instrument_key(self, instrument_key: str) -> dict:
        response = requests.get(
            UPSTOX_LTP_URL, params={"instrument_key": instrument_key}, headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    def get_latest_quote(self, symbol: str) -> Bar:
        raise NotImplementedError(
            "Requires a symbol -> Upstox instrument_key mapping, not yet built. "
            "Use get_latest_quote_by_instrument_key() directly for now."
        )

    def get_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[Bar]:
        raise NotImplementedError(
            "Historical data is sourced from YFinanceLoader in this project, not Upstox."
        )

    def get_universe(self) -> list[str]:
        raise NotImplementedError

    def get_corporate_actions(self, symbol: str, start: datetime, end: datetime) -> list[dict]:
        raise NotImplementedError
