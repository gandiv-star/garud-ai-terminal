from datetime import datetime, timedelta

from config.settings import load_settings
from data.yfinance_loader import YFinanceLoader


def main() -> None:
    settings = load_settings()
    print(f"Garud AI Terminal — mode: {settings.trading_mode.value}")
    print(f"Kill switch enabled: {settings.kill_switch_enabled}")

    print("\nTesting YFinanceLoader with RELIANCE (last 5 days)...")
    try:
        loader = YFinanceLoader()
        end = datetime.now()
        start = end - timedelta(days=5)
        bars = loader.get_historical_bars("RELIANCE", start, end)
        print(f"Fetched {len(bars)} bars.")
        if bars:
            last = bars[-1]
            print(f"Latest: {last.timestamp.date()} close={last.close}")
    except Exception as e:
        print(f"YFinanceLoader test failed: {e}")


if __name__ == "__main__":
    main()
