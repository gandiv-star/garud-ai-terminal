from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from config.settings import load_settings
from data.data_validator import DataValidator
from data.yfinance_loader import YFinanceLoader
from database.db import Database
from features.feature_engine import FeatureEngine
from regime.regime_engine import RegimeEngine
from sector.sector_analysis import SectorAnalysisEngine
from strategies.momentum import MomentumStrategy

st.set_page_config(page_title="Garud AI Terminal", layout="wide")

settings = load_settings()

st.title("Garud AI Terminal")
st.caption("Skeleton-stage dashboard — shows what's actually built so far")

col1, col2 = st.columns(2)
col1.metric("Mode", settings.trading_mode.value)
col2.metric("Kill switch", "Enabled" if settings.kill_switch_enabled else "Disabled")

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
                [
                    {
                        "sector": r.sector,
                        "sector_return_%": r.sector_return,
                        "index_return_%": r.index_return,
                        "relative_strength": round(r.relative_strength, 2),
                    }
                    for r in rankings
                ]
            )
            st.bar_chart(df.set_index("sector")["relative_strength"])
            st.dataframe(df)
        except Exception as e:
            st.error(f"Sector ranking failed: {e}")

st.divider()
st.subheader("Momentum strategy signal")
mom_symbol = st.text_input("NSE symbol for signal", value="RELIANCE", key="mom_symbol")
if st.button("Get momentum signal"):
    with st.spinner(f"Analyzing {mom_symbol}..."):
        try:
            loader = YFinanceLoader()
            end = datetime.now()
            start = end - timedelta(days=60)
            bars = loader.get_historical_bars(mom_symbol, start, end)

            fe = FeatureEngine()
            features = fe.compute(mom_symbol, bars)

            regime_engine = RegimeEngine()
            regime = regime_engine.detect()

            strategy = MomentumStrategy()
            signal = strategy.evaluate(mom_symbol, features, regime)

            c1, c2 = st.columns(2)
            c1.metric("Decision", signal.decision.value)
            c2.metric("Confidence", f"{signal.confidence:.2f}")
            st.write(signal.rationale)
            with st.expander("Feature details"):
                st.json(features.__dict__)
        except Exception as e:
            st.error(f"Signal generation failed: {e}")

st.divider()
st.subheader("Fetch historical data")
symbol = st.text_input("NSE symbol", value="RELIANCE")
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
                df = pd.DataFrame(
                    [{"date": b.timestamp.date(), "close": b.close, "volume": b.volume} for b in bars]
                )
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
