from datetime import datetime, timedelta

from config.settings import load_settings
from data.yfinance_loader import YFinanceLoader
from features.feature_engine import FeatureEngine
from regime.regime_engine import RegimeEngine
from scoring.ai_scoring_engine import AIScoringEngine
from risk.risk_engine import RiskEngine, TradeProposal
from risk.position_sizing import SizingInput, calculate_quantity
from risk.stop_loss import calculate_atr_stop
from strategies.momentum import MomentumStrategy
from strategies.breakout import BreakoutStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.relative_strength import RelativeStrengthStrategy
from strategies.volume_breakout import VolumeBreakoutStrategy
from strategies.volatility_expansion import VolatilityExpansionStrategy
from strategies.regime_adaptive import RegimeAdaptiveStrategy

print("--- Verify: Full pipeline (Data -> Score -> Risk) on RELIANCE ---")
try:
    settings = load_settings()
    loader = YFinanceLoader()
    end = datetime.now()
    start = end - timedelta(days=60)
    bars = loader.get_historical_bars("RELIANCE", start, end)

    fe = FeatureEngine()
    features = fe.compute("RELIANCE", bars)

    regime_engine = RegimeEngine()
    regime = regime_engine.detect()
    print(f"Regime: {regime.regime.value}")

    strategies = [
        MomentumStrategy(), BreakoutStrategy(), TrendFollowingStrategy(),
        MeanReversionStrategy(), RelativeStrengthStrategy(), VolumeBreakoutStrategy(),
        VolatilityExpansionStrategy(), RegimeAdaptiveStrategy(),
    ]
    signals = [s.evaluate("RELIANCE", features, regime) for s in strategies]

    scorer = AIScoringEngine()
    candidate = scorer.score("RELIANCE", signals)
    print(f"AI Score: {candidate.score}/100")

    entry_price = features.price
    stop_result = calculate_atr_stop(entry_price, features.atr, multiplier=2.0)
    stop_price = stop_result.stop_price
    sizing = SizingInput(
        available_capital=100000.0, max_risk_pct=settings.risk.max_risk_per_trade_pct,
        entry_price=entry_price, stop_price=stop_price, lot_size=1,
    )
    quantity = calculate_quantity(sizing)
    print(f"Proposed: entry={entry_price} stop={stop_price:.2f} qty={quantity}")

    proposal = TradeProposal(
        symbol="RELIANCE", quantity=quantity, entry_price=entry_price,
        stop_price=stop_price, sector="Energy",
    )
    risk_engine = RiskEngine(settings.risk)

    print("\n--- Case A: normal conditions (should APPROVE if score/qty reasonable) ---")
    verdict = risk_engine.evaluate(
        proposal=proposal, available_capital=100000.0, current_daily_pnl_pct=0.0,
        current_portfolio_drawdown_pct=0.0, current_sector_exposure_pct=0.0, open_position_count=0,
    )
    print(f"approved={verdict.approved} reasons={verdict.rejection_reasons}")

    print("\n--- Case B: daily loss limit already breached (-5%, limit is -3%) — MUST REJECT ---")
    verdict2 = risk_engine.evaluate(
        proposal=proposal, available_capital=100000.0, current_daily_pnl_pct=-5.0,
        current_portfolio_drawdown_pct=0.0, current_sector_exposure_pct=0.0, open_position_count=0,
    )
    print(f"approved={verdict2.approved} reasons={verdict2.rejection_reasons}")

    print("\n--- Case C: max open positions already reached (10/10) — MUST REJECT ---")
    verdict3 = risk_engine.evaluate(
        proposal=proposal, available_capital=100000.0, current_daily_pnl_pct=0.0,
        current_portfolio_drawdown_pct=0.0, current_sector_exposure_pct=0.0, open_position_count=10,
    )
    print(f"approved={verdict3.approved} reasons={verdict3.rejection_reasons}")

    print(f"\nAI Score was {candidate.score}/100 — final decision would combine this with the risk verdict above.")
except Exception as e:
    print(f"FAILED: {e}")
