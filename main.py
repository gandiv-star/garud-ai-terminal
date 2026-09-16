from datetime import datetime, timedelta

from config.settings import load_settings
from data.data_validator import DataValidator
from data.data_loader import Bar
from data.yfinance_loader import YFinanceLoader
from database.db import Database
from database.models import TradeRecord, AuditEvent
from regime.regime_engine import RegimeEngine


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
        Bar(symbol="FAKE", timestamp=datetime.now(), open=100, high=90, low=95, close=92, volume=1000)
    ]
    result = validator.validate_bars("FAKE", bad_bars)
    print(f"Valid: {result.is_valid}, issues: {result.issues}")

    print("\n--- Test 3: empty data ---")
    result = validator.validate_bars("EMPTY", [])
    print(f"Valid: {result.is_valid}, issues: {result.issues}")

    print("\n--- Test 4: database save + retrieve ---")
    try:
        db = Database(settings)
        db.connect()
        trade = TradeRecord(
            internal_order_id="test-order-001", symbol="RELIANCE", strategy_name="momentum",
            strategy_version="0.1.0", decision="BUY", ai_score=87.0, entry_price=1250.0,
            stop_price=1220.0, target_price=1310.0, quantity=10, risk_amount=300.0,
            regime="MODERATE_BULL", sector="Energy", timestamp=datetime.now(),
        )
        db.save_trade(trade)
        audit = AuditEvent(
            timestamp=datetime.now(), event_type="TRADE_DECISION", symbol="RELIANCE",
            payload={"decision": "BUY", "reason": "test entry"},
        )
        db.save_audit_event(audit)
        saved_trades = db.get_trades()
        print(f"Trades in DB: {len(saved_trades)}")
        if saved_trades:
            t = saved_trades[0]
            print(f"Latest trade: {t.symbol} {t.decision} qty={t.quantity} score={t.ai_score}")
    except Exception as e:
        print(f"Test 4 failed: {e}")

    print("\n--- Test 5: market regime detection (NIFTY) ---")
    try:
        regime_engine = RegimeEngine()
        assessment = regime_engine.detect()
        print(f"Regime: {assessment.regime.value}")
        print(f"Confidence: {assessment.confidence}")
        print(f"Risk level: {assessment.risk_level.value}")
        print(f"Features: {assessment.supporting_features}")
    except Exception as e:
        print(f"Test 5 failed: {e}")


if __name__ == "__main__":
    main()
