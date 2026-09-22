from brokers.upstox_broker import UpstoxBroker

print("--- Verify: Upstox read-only endpoints (funds/positions/holdings) ---")
try:
    broker = UpstoxBroker()
    broker.authenticate()
    print("Token present, authenticate() passed.")

    print("\n--- Funds ---")
    funds = broker.get_funds()
    print(funds)

    print("\n--- Positions ---")
    positions = broker.get_positions()
    print(positions)

    print("\n--- Holdings ---")
    holdings = broker.get_holdings()
    print(holdings)
except Exception as e:
    print(f"FAILED: {e}")
    print("If this is a 401/403: could be an expired token (refresh via Upstox login) "
          "OR a static-IP whitelist mismatch (GitHub Actions IP isn't fixed).")
