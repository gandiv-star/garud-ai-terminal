from notifications.telegram_alert import TelegramAlerter

print("--- Verify: Telegram Alert ---")
alerter = TelegramAlerter()
print(f"Configured: {alerter.is_configured}")
if alerter.is_configured:
    ok = alerter.send("🦅 *Garud AI Terminal* — test alert. If you see this, Telegram alerts are working.")
    print(f"Send result: {ok}")
else:
    print("Not configured — check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID secrets.")
