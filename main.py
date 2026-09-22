from security.secrets_manager import SecretsManager

print("--- Diagnostic: is the token being read correctly (masked, safe to share) ---")
try:
    token = SecretsManager.get("BROKER_ACCESS_TOKEN")
    print(f"Token length: {len(token)}")
    print(f"Starts with: {token[:6]}...")
    print(f"Ends with: ...{token[-4:]}")
    print(f"Has leading/trailing whitespace: {token != token.strip()}")
except Exception as e:
    print(f"FAILED: {e}")

print("\n--- Retry funds call with explicit error body ---")
try:
    import requests
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token.strip()}"}
    response = requests.get("https://api.upstox.com/v2/user/get-funds-and-margin", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")
except Exception as e:
    print(f"FAILED: {e}")
