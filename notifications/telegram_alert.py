"""
Telegram alerts.

Best-effort, non-blocking notifications for key events (trade logged,
position closed, stop-loss hit, kill switch triggered). A failure here
must NEVER break the calling flow — trading/paper-trading logic must
keep working even if Telegram is unreachable or unconfigured.
"""

import requests

from security.secrets_manager import SecretsManager

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramAlerter:
    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        self.bot_token = bot_token or SecretsManager.get("TELEGRAM_BOT_TOKEN", required=False)
        self.chat_id = chat_id or SecretsManager.get("TELEGRAM_CHAT_ID", required=False)

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send(self, message: str) -> bool:
        """Returns True on success, False on any failure — never raises."""
        if not self.is_configured:
            return False
        try:
            url = TELEGRAM_API_URL.format(token=self.bot_token)
            response = requests.post(
                url,
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False
          
