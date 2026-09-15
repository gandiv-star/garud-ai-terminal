from datetime import datetime, timedelta

from config.settings import load_settings
from data.data_validator import DataValidator
from data.data_loader import Bar
from data.yfinance_loader import YFinanceLoader


def main() -> None:
    settings = load_settings()
    print(f"Garud AI Terminal — mode: {settings.trading_mode.value}")
    print(f"Kill switch enabled: {settings.kill_switch_enabled}")

    validator = DataValidator()

    print("\n--- Test 1: real data (RELIANCE, last 5 days) ---")
    try:
        loader = YFinanceLoader()
        end = datetime.now()
        start = end - timedelta(days=5)
        bars = loader.get_historical_bars("RELIANCE", start, end)
        print(f"Fetched {len(bars)} bars.")
        result = validator.validate_bars("RELIANCE", bars)
        print(f"Valid: {result.is_valid}, issues: {result.issues}")
    except Exception as e:
        print(f"Test 1 failed: {e}")

    print("\n--- Test 2: deliberately BAD data (high < low) ---")
    bad_bars = [
        Bar(
            symbol="FAKE",
            timestamp=datetime.now(),
            open=100,
            high=90,   # high < low — invalid on purpose
            low=95,
            close=92,
            volume=1000,
        )
    ]
    result = validator.validate_bars("FAKE", bad_bars)
    print(f"Valid: {result.is_valid}, issues: {result.issues}")

    print("\n--- Test 3: empty data ---")
    result = validator.validate_bars("EMPTY", [])
    print(f"Valid: {result.is_valid}, issues: {result.issues}")


if __name__ == "__main__":
    main()
