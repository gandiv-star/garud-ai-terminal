import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from audit.audit_trail import AuditTrail
from config.settings import load_settings
from core.constants import Decision
from data.data_validator import DataValidator
from data.yfinance_loader import YFinanceLoader
from database.db import Database
from database.models import TradeRecord
from features.feature_engine import FeatureEngine
from llm.explainability import ExplainabilityEngine
from regime.regime_engine import RegimeEngine
from risk.position_sizing import SizingInput, calculate_quantity
from risk.risk_engine import RiskEngine, TradeProposal
from risk.stop_loss import calculate_atr_stop
from scoring.ai_scoring_engine import AIScoringEngine
from sector.sector_analysis import SectorAnalysisEngine
from strategies.breakout import BreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.regime_adaptive import RegimeAdaptiveStrategy
from strategies.relative_strength import RelativeStrengthStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.volatility_expansion import VolatilityExpansionStrategy
from strategies.volume_breakout import VolumeBreakoutStrategy

st.set_page_config(page_title="Garud AI Terminal", layout="wide")

settings = load_settings()

st.title("Garud AI Terminal")
st.caption("Skeleton-stage dashboard — shows what's actually built so far")

col1, col2 = st.columns(2)
col1.metric("Mode", settings.trading_mode.value)
col2.metric("Kill switch", "Enabled" if settings.kill_switch_enabled else "Disabled")

st.divider()
st.subheader("Full analysis: Data -> Regime -> Strategies -> Score -> Risk -> Explanation")
fa_symbol = st.text_input("NSE symbol", value="RELIANCE", key="full_analysis_symbol")
fa_sector = st.text_input("Sector", value="Energy", key="full_analysis_sector")
fa_capital = st.number_input("Available capital (Rs)", value=100000.0, step=10000.0)
fa_open_positions = st.number_input("Current open positions", value=0, min_value=0, max_value=20, step=1)

if st.button("Run full analysis"):
    with st.spinner(f"Analyzing {fa_symbol}..."):
        try:
            loader = YFinanceLoader()
            end = datetime.now()
            start = end - timedelta(days=60)
            bars = loader.get_historical_bars(fa_symbol, start, end)

            fe = FeatureEngine()
            features = fe.compute(fa_symbol, bars)

            regime_engine = RegimeEngine()
            regime = regime_engine.detect()

            strategies = [
                MomentumStrategy(), BreakoutStrategy(), TrendFollowingStrategy(),
                MeanReversionStrategy(), RelativeStrengthStrategy(), VolumeBreakoutStrategy(),
                VolatilityExpansionStrategy(), RegimeAdaptiveStrategy(),
            ]
            signals = [s.evaluate(fa_symbol, features, regime) for s in strategies]

            scorer = AIScoringEngine()
            candidate = scorer.score(fa_symbol, signals)

            overall_decision = Decision.NO_TRADE
            if candidate.score >= 65:
                overall_decision = Decision.BUY
            elif candidate.score <= 35:
                overall_decision = Decision.SELL

            result = {
                "symbol": fa_symbol, "sector": fa_sector, "features": features,
                "regime": regime, "signals": signals, "candidate": candidate,
                "overall_decision": overall_decision,
            }

            if features.price is not None and features.atr is not None:
                stop_result = calculate_atr_stop(features.price, features.atr, multiplier=2.0)
                sizing = SizingInput(
                    available_capital=fa_capital, max_risk_pct=settings.risk.max_risk_per_trade_pct,
                    entry_price=features.price, stop_price=stop_result.stop_price,
                )
                quantity = calculate_quantity(sizing)
                proposal = TradeProposal(
                    symbol=fa_symbol, quantity=quantity, entry_price=features.price,
                    stop_price=stop_result.stop_price, sector=fa_sector,
                )
                risk_engine = RiskEngine(settings.risk)
                verdict = risk_engine.evaluate(
                    proposal=proposal, available_capital=fa_capital, current_daily_pnl_pct=0.0,
                    current_portfolio_drawdown_pct=0.0, current_sector_exposure_pct=0.0,
                    open_position_count=fa_open_positions,
                )
                result.update({"stop_price": stop_result.stop_price, "quantity": quantity, "verdict": verdict})

            st.session_state["last_analysis"] = result
        except Exception as e:
            st.error(f"Full analysis failed: {e}")

if "last_analysis" in st.session_state:
    r = st.session_state["last_analysis"]
    c1, c2 = st.columns(2)
    c1.metric("Regime", r["regime"].regime.value)
    c2.metric("AI Score", f"{r['candidate'].score}/100")

    st.write("**Strategy signals:**")
    sig_df = pd.DataFrame(
        [{"strategy": s.strategy_name, "decision": s.decision.value, "confidence": s.confidence} for s in r["signals"]]
    )
    st.dataframe(sig_df)

    if "verdict" in r:
        st.write("**Proposed trade:**")
        c3, c4, c5 = st.columns(3)
        c3.metric("Entry", f"{r['features'].price:.2f}")
        c4.metric("Stop", f"{r['stop_price']:.2f}")
        c5.metric("Quantity", r["quantity"])

        if r["verdict"].approved:
            st.success(f"Risk Engine: APPROVED")
        else:
            st.error(f"Risk Engine: REJECTED — {r['verdict'].rejection_reasons}")

        exp_engine = ExplainabilityEngine()
        explanation = exp_engine.explain(
            symbol=r["symbol"], decision=r["overall_decision"], candidate_score=r["candidate"],
            regime=r["regime"], sector=r["sector"], entry_price=r["features"].price,
            stop_price=r["stop_price"], quantity=r["quantity"],
        )
        st.write("**Trade explanation:**")
        st.markdown(
            f"- **Decision:** {explanation.decision.value}\n"
            f"- **AI Score:** {explanation.ai_score}/100\n"
            f"- **Regime:** {explanation.regime.value}\n"
            f"- **Sector:** {explanation.sector}\n"
            f"- **Risk:** Rs.{explanation.risk_amount}\n"
            f"- **Reason:** {explanation.reason}"
        )

        can_log = settings.trading_mode.value != "BACKTEST"
        if not can_log:
            st.info("Mode is BACKTEST — switch TRADING_MODE to PAPER to log trades.")
        elif r["overall_decision"] != Decision.NO_TRADE and r["verdict"].approved:
            if st.button("Log as Paper Trade"):
                try:
                    db = Database(settings)
                    db.connect()
                    trail = AuditTrail(db)
                    trade = TradeRecord(
                        internal_order_id=f"garud-{uuid.uuid4()}", symbol=r["symbol"],
                        strategy_name="composite", strategy_version="0.1.0",
                        decision=r["overall_decision"].value, ai_score=r["candidate"].score,
                        entry_price=r["features"].price, stop_price=r["stop_price"], target_price=None,
                        quantity=r["quantity"], risk_amount=explanation.risk_amount,
                        regime=r["regime"].regime.value, sector=r["sector"],
                        timestamp=datetime.now(timezone.utc),
                    )
                    db.save_trade(trade)
                    trail.record(
                        symbol=r["symbol"], event_type="PAPER_TRADE_LOGGED",
                        decision=r["overall_decision"].value, ai_score=r["candidate"].score,
                        reason=explanation.reason,
                    )
                    st.success(f"Paper trade logged: {trade.internal_order_id}")
                except Exception as e:
                    st.error(f"Logging failed: {e}")

st.divider()
st.subheader("Market regime (NIFTY)")
if st.button("Detect current regime"):
    with st.spinner("Fetching NIFTY data..."):
        try:
            engine = RegimeEngine()
            assessment = engine.detect()
            c1, c2, c3 = st.columns(3)
            c1.metric("Regime", assessment.regime.value)
            c2.metric("Confidence", f"{assessment.confidence:.2f}")
            c3.metric("Risk level", assessment.risk_level.value)
            st.json(assessment.supporting_features)
        except Exception as e:
            st.error(f"Regime detection failed: {e}")

st.divider()
st.subheader("Sector strength")
if st.button("Rank sectors (1 month)"):
    with st.spinner("Fetching sector stocks..."):
        try:
            sector_engine = SectorAnalysisEngine()
            rankings = sector_engine.rank_sectors()
            df = pd.DataFrame(
                [{"sector": r.sector, "sector_return_%": r.sector_return, "index_return_%": r.index_return,
                  "relative_strength": round(r.relative_strength, 2)} for r in rankings]
            )
            st.bar_chart(df.set_index("sector")["relative_strength"])
            st.dataframe(df)
        except Exception as e:
            st.error(f"Sector ranking failed: {e}")

st.divider()
st.subheader("Fetch historical data")
symbol = st.text_input("NSE symbol", value="RELIANCE", key="fetch_symbol")
days = st.slider("Days of history", 5, 90, 30)
if st.button("Fetch data"):
    with st.spinner(f"Fetching {symbol}..."):
        try:
            loader = YFinanceLoader()
            validator = DataValidator()
            end = datetime.now()
            start = end - timedelta(days=days)
            bars = loader.get_historical_bars(symbol, start, end)
            result = validator.validate_bars(symbol, bars)
            st.write(f"Fetched {len(bars)} bars. Valid: {result.is_valid}")
            if result.issues:
                st.warning(result.issues)
            if bars:
                df = pd.DataFrame([{"date": b.timestamp.date(), "close": b.close, "volume": b.volume} for b in bars])
                st.line_chart(df.set_index("date")["close"])
                st.dataframe(df)
        except Exception as e:
            st.error(f"Fetch failed: {e}")

st.divider()
st.subheader("Logged trades")
try:
    db = Database(settings)
    db.connect()
    trades = db.get_trades()
    if trades:
        df = pd.DataFrame([t.__dict__ for t in trades])
        st.dataframe(df)
    else:
        st.info("No trades logged yet.")
except Exception as e:
    st.error(f"Database read failed: {e}")
