import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from analytics.performance_metrics import PerformanceCalculator
from analytics.strategy_health import StrategyHealthMonitor
from audit.audit_trail import AuditTrail
from backtest.backtest_engine import BacktestEngine, ChargeModel
from config.settings import load_settings
from core.constants import Decision
from data.data_validator import DataValidator
from data.yfinance_loader import YFinanceLoader
from database.db import Database
from database.models import TradeRecord
from features.feature_engine import FeatureEngine
from llm.explainability import ExplainabilityEngine
from portfolio.correlation_engine import CorrelationEngine
from portfolio.portfolio_engine import PortfolioEngine
from regime.regime_engine import RegimeEngine
from risk.position_sizing import SizingInput, calculate_quantity
from risk.risk_engine import RiskEngine, TradeProposal
from risk.stop_loss import calculate_atr_stop
from scoring.ai_scoring_engine import AIScoringEngine
from sector.sector_analysis import SECTOR_STOCKS, SectorAnalysisEngine
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

if "kill_switch_engaged" not in st.session_state:
    st.session_state["kill_switch_engaged"] = not settings.kill_switch_enabled

col1, col2, col3 = st.columns(3)
col1.metric("Mode", settings.trading_mode.value)
if st.session_state["kill_switch_engaged"]:
    col2.metric("Kill switch", "TRIGGERED")
    if col3.button("Reset (manual)"):
        st.session_state["kill_switch_engaged"] = False
        st.rerun()
else:
    col2.metric("Kill switch", "Enabled")
    if col3.button("TRIGGER KILL SWITCH", type="primary"):
        st.session_state["kill_switch_engaged"] = True
        st.rerun()

if st.session_state["kill_switch_engaged"]:
    st.error("Kill switch is TRIGGERED — all new trade actions below are blocked until manually reset.")

tab_analysis, tab_scanner, tab_positions, tab_backtest, tab_market = st.tabs(
    ["Analysis", "Scanner", "Positions", "Backtest", "Market Data"]
)

with tab_analysis:
    st.subheader("Full analysis: Data -> Regime -> Strategies -> Score -> Risk -> Explanation")
    fa_symbol = st.text_input("NSE symbol", value="RELIANCE", key="full_analysis_symbol")
    fa_sector = st.text_input("Sector", value="Energy", key="full_analysis_sector")
    fa_capital = st.number_input("Available capital (Rs)", value=100000.0, step=10000.0)
    fa_force_buy = st.checkbox("Force BUY for testing (bypasses real signal — not a real trade decision)")

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
                if fa_force_buy:
                    overall_decision = Decision.BUY

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

                    db_for_risk = Database(settings)
                    db_for_risk.connect()
                    all_trades_for_risk = db_for_risk.get_trades(limit=200)
                    closed_for_risk = [t for t in all_trades_for_risk if t.exit_price is not None]
                    open_for_risk = [t for t in all_trades_for_risk if t.exit_price is None]

                    today = datetime.now(timezone.utc).date()
                    today_pnl = sum(
                        t.realized_pnl for t in closed_for_risk
                        if t.exit_timestamp is not None and t.exit_timestamp.date() == today
                    )
                    real_daily_pnl_pct = (today_pnl / fa_capital) * 100 if fa_capital > 0 else 0.0

                    sector_value = sum(t.entry_price * t.quantity for t in open_for_risk if t.sector == fa_sector)
                    real_sector_exposure_pct = (sector_value / fa_capital) * 100 if fa_capital > 0 else 0.0

                    sorted_closed = sorted(closed_for_risk, key=lambda t: t.exit_timestamp)
                    equity_curve = fa_capital
                    peak_equity = equity_curve
                    for ct in sorted_closed:
                        equity_curve += ct.realized_pnl
                        peak_equity = max(peak_equity, equity_curve)
                    real_drawdown_pct = (peak_equity - equity_curve) / peak_equity * 100 if peak_equity > 0 else 0.0

                    risk_engine = RiskEngine(settings.risk)
                    verdict = risk_engine.evaluate(
                        proposal=proposal, available_capital=fa_capital, current_daily_pnl_pct=real_daily_pnl_pct,
                        current_portfolio_drawdown_pct=real_drawdown_pct, current_sector_exposure_pct=real_sector_exposure_pct,
                        open_position_count=len(open_for_risk),
                    )
                    result.update({
                        "stop_price": stop_result.stop_price, "quantity": quantity, "verdict": verdict,
                        "real_daily_pnl_pct": real_daily_pnl_pct, "real_sector_exposure_pct": real_sector_exposure_pct,
                        "open_position_count": len(open_for_risk), "real_drawdown_pct": real_drawdown_pct,
                    })

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

            st.write("**Real risk inputs used (from your paper-trade history):**")
            c6, c7, c8, c9 = st.columns(4)
            c6.metric("Today's P&L", f"{r['real_daily_pnl_pct']:.2f}%")
            c7.metric(f"{r['sector']} exposure", f"{r['real_sector_exposure_pct']:.2f}%")
            c8.metric("Open positions", r["open_position_count"])
            c9.metric("Portfolio drawdown", f"{r['real_drawdown_pct']:.2f}%")

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
            if st.session_state.get("kill_switch_engaged"):
                st.warning("Kill switch is triggered — logging blocked.")
            elif not can_log:
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

with tab_scanner:
    st.subheader("Stock scanner + portfolio selection")
    st.caption("Scans a small universe, scores each, then Portfolio Engine picks the best combination under sector/correlation limits.")
    default_universe = "HDFCBANK,TCS,SUNPHARMA,MARUTI,TATASTEEL,HINDUNILVR,RELIANCE,DLF"
    scan_universe_input = st.text_input("Universe (comma-separated NSE symbols)", value=default_universe)
    scan_open_positions_input = st.text_input("Existing open position symbols (comma-separated, optional)", value="")
    scan_max_sector_pct = st.number_input("Max sector exposure %", value=settings.risk.max_sector_exposure_pct, key="scan_max_sector")

    symbol_to_sector = {sym: sector for sector, syms in SECTOR_STOCKS.items() for sym in syms}

    if st.button("Scan universe"):
        with st.spinner("Scanning (this can take a little while)..."):
            try:
                symbols = [s.strip().upper() for s in scan_universe_input.split(",") if s.strip()]
                open_positions_list = [s.strip().upper() for s in scan_open_positions_input.split(",") if s.strip()]

                regime_engine = RegimeEngine()
                regime = regime_engine.detect()
                st.write(f"Regime: **{regime.regime.value}**")

                strategies = [
                    MomentumStrategy(), BreakoutStrategy(), TrendFollowingStrategy(),
                    MeanReversionStrategy(), RelativeStrengthStrategy(), VolumeBreakoutStrategy(),
                    VolatilityExpansionStrategy(), RegimeAdaptiveStrategy(),
                ]
                scorer = AIScoringEngine()
                loader = YFinanceLoader()
                fe = FeatureEngine()

                candidates = []
                end = datetime.now()
                start = end - timedelta(days=60)
                for sym in symbols:
                    try:
                        bars = loader.get_historical_bars(sym, start, end)
                        features = fe.compute(sym, bars)
                        signals = [s.evaluate(sym, features, regime) for s in strategies]
                        candidate = scorer.score(sym, signals)
                        candidates.append(candidate)
                    except Exception as sym_e:
                        st.warning(f"{sym}: skipped ({sym_e})")

                if not candidates:
                    st.info("No candidates scored.")
                else:
                    scan_df = pd.DataFrame(
                        [{"symbol": c.symbol, "sector": symbol_to_sector.get(c.symbol, "Unknown"), "score": c.score} for c in candidates]
                    ).sort_values("score", ascending=False)
                    st.write("**Scored candidates (all):**")
                    st.dataframe(scan_df)

                    corr_engine = CorrelationEngine()
                    portfolio_engine = PortfolioEngine(corr_engine, max_correlation=0.8)
                    decision = portfolio_engine.select(
                        candidates=candidates, open_positions=open_positions_list,
                        sector_by_symbol=symbol_to_sector, max_sector_exposure_pct=scan_max_sector_pct,
                    )
                    st.write("**Portfolio Engine — accepted:**")
                    st.write(decision.accepted_symbols if decision.accepted_symbols else "(none)")
                    st.write("**Portfolio Engine — rejected (with reason):**")
                    st.json(decision.rejected_symbols)
            except Exception as e:
                st.error(f"Scan failed: {e}")

with tab_positions:
    st.subheader("Open paper positions")
    try:
        db = Database(settings)
        db.connect()
        all_trades = db.get_trades(limit=200)
        open_trades = [t for t in all_trades if t.exit_price is None]

        if not open_trades:
            st.info("No open paper positions.")
        else:
            for t in open_trades:
                with st.container():
                    oc1, oc2, oc3, oc4, oc5 = st.columns([2, 1, 1, 1, 2])
                    oc1.write(f"**{t.symbol}**")
                    oc2.write(f"Entry: {t.entry_price:.2f}")
                    oc3.write(f"Qty: {t.quantity}")
                    oc4.write(f"Stop: {t.stop_price:.2f}")
                    if oc5.button("Close at current price", key=f"close_{t.internal_order_id}"):
                        if st.session_state.get("kill_switch_engaged"):
                            st.warning("Kill switch is triggered — cannot close positions.")
                        else:
                            try:
                                loader = YFinanceLoader()
                                end = datetime.now()
                                start = end - timedelta(days=5)
                                bars = loader.get_historical_bars(t.symbol, start, end)
                                if not bars:
                                    st.error("Could not fetch current price.")
                                else:
                                    current_price = bars[-1].close
                                    charge_model = ChargeModel()
                                    buy_turnover = t.entry_price * t.quantity
                                    sell_turnover = current_price * t.quantity
                                    charges = charge_model.buy_charges(buy_turnover) + charge_model.sell_charges(sell_turnover)
                                    gross_pnl = (current_price - t.entry_price) * t.quantity
                                    net_pnl = gross_pnl - charges

                                    db.update_trade_exit(
                                        internal_order_id=t.internal_order_id, exit_price=current_price,
                                        exit_timestamp=datetime.now(timezone.utc), realized_pnl=round(net_pnl, 2),
                                    )
                                    trail = AuditTrail(db)
                                    trail.record(
                                        symbol=t.symbol, event_type="PAPER_TRADE_CLOSED",
                                        exit_price=current_price, realized_pnl=round(net_pnl, 2),
                                    )
                                    st.success(f"Closed {t.symbol} at {current_price:.2f} — net P&L: Rs.{net_pnl:.2f}")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Close failed: {e}")
    except Exception as e:
        st.error(f"Loading open positions failed: {e}")

    st.divider()
    st.subheader("Equity curve")
    try:
        db_eq = Database(settings)
        db_eq.connect()
        all_trades_eq = db_eq.get_trades(limit=200)
        closed_eq = sorted([t for t in all_trades_eq if t.exit_price is not None], key=lambda t: t.exit_timestamp)
        if closed_eq:
            base_capital = 100000.0
            equity = base_capital
            points = [{"trade_number": 0, "equity": equity}]
            for i, t in enumerate(closed_eq, start=1):
                equity += t.realized_pnl
                points.append({"trade_number": i, "equity": equity})
            eq_df = pd.DataFrame(points)
            st.line_chart(eq_df.set_index("trade_number")["equity"])
            st.caption(f"Starting capital assumed: Rs.{base_capital:,.0f} — x-axis is trade number, not calendar time.")
        else:
            st.info("No closed trades yet — equity curve will appear once you close some paper trades.")
    except Exception as e:
        st.error(f"Equity curve failed: {e}")

    st.divider()
    st.subheader("Closed paper trades — performance")
    try:
        db = Database(settings)
        db.connect()
        all_trades = db.get_trades(limit=200)
        closed_trades = [t for t in all_trades if t.exit_price is not None]

        if not closed_trades:
            st.info("No closed paper trades yet.")
        else:
            perf_calc = PerformanceCalculator()
            closed_dicts = [
                {"net_pnl": t.realized_pnl, "gross_pnl": (t.exit_price - t.entry_price) * t.quantity, "exit_date": t.exit_timestamp}
                for t in closed_trades
            ]
            summary = perf_calc.summarize(closed_dicts, starting_capital=100000.0)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Closed trades", summary.trade_count)
            c2.metric("Net P&L", f"Rs.{summary.net_pnl}")
            c3.metric("Win rate", f"{summary.win_rate * 100:.1f}%")
            c4.metric("Profit factor", summary.profit_factor)

            df = pd.DataFrame([t.__dict__ for t in closed_trades])
            st.dataframe(df)
    except Exception as e:
        st.error(f"Loading closed trades failed: {e}")

with tab_backtest:
    st.subheader("Backtest (Momentum strategy)")
    bt_symbol = st.text_input("NSE symbol", value="RELIANCE", key="bt_symbol")
    bt_days = st.slider("Backtest period (days)", 90, 730, 365, key="bt_days")
    bt_capital = st.number_input("Starting capital (Rs)", value=100000.0, step=10000.0, key="bt_capital")

    if st.button("Run backtest"):
        with st.spinner("Running backtest..."):
            try:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=bt_days)
                bt_engine = BacktestEngine(ChargeModel())
                bt_result = bt_engine.run(bt_symbol, start_date, end_date, capital=bt_capital)

                perf_calc = PerformanceCalculator()
                summary = perf_calc.summarize(bt_result.trades, starting_capital=bt_capital)

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Trades", summary.trade_count)
                c2.metric("Net P&L", f"Rs.{summary.net_pnl}")
                c3.metric("Win rate", f"{summary.win_rate * 100:.1f}%")
                c4.metric("Max drawdown", f"{summary.max_drawdown_pct}%")

                c5, c6, c7 = st.columns(3)
                c5.metric("Profit factor", summary.profit_factor)
                c6.metric("Expectancy/trade", f"Rs.{summary.expectancy}")
                c7.metric("Total charges", f"Rs.{bt_result.total_charges}")

                if bt_result.trades:
                    trades_df = pd.DataFrame([t.__dict__ for t in bt_result.trades])
                    st.dataframe(trades_df)

                    health_monitor = StrategyHealthMonitor()
                    health = health_monitor.assess("momentum", bt_result.trades, min_trades=6)
                    st.write(f"**Strategy health:** {health.notes}")
                    if health.historical_win_rate or health.recent_win_rate:
                        hc1, hc2 = st.columns(2)
                        hc1.metric("Recent win rate", f"{health.recent_win_rate * 100:.1f}%")
                        hc2.metric("Historical win rate", f"{health.historical_win_rate * 100:.1f}%")
                else:
                    st.info("No trades in this window — momentum only enters during bull-favorable regimes.")
            except Exception as e:
                st.error(f"Backtest failed: {e}")

with tab_market:
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
