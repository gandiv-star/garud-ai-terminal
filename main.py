from datetime import datetime, timedelta

from backtest.backtest_engine import BacktestEngine, ChargeModel

print("--- Verify: BacktestEngine on RELIANCE, last 1 year, MomentumStrategy ---")
try:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    engine = BacktestEngine(ChargeModel())
    result = engine.run("RELIANCE", start_date, end_date, capital=100000.0)

    print(f"Trade count: {result.trade_count}")
    print(f"Gross P&L: {result.gross_pnl}")
    print(f"Total charges: {result.total_charges}")
    print(f"Net P&L: {result.net_pnl}")

    if result.trades:
        print("\nIndividual trades:")
        for t in result.trades:
            print(
                f"  {t.entry_date.date()} -> {t.exit_date.date()} | "
                f"entry={t.entry_price} exit={t.exit_price} qty={t.quantity} | "
                f"net={t.net_pnl} ({t.exit_reason})"
            )
    else:
        print("\nNo trades triggered in this window — Momentum strategy only enters in "
              "bull-favorable regimes, so a bearish/sideways year can legitimately give zero trades.")
except Exception as e:
    print(f"FAILED: {e}")
