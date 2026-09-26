from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

import yfinance as yf

from core.constants import Decision, MarketRegime, RiskLevel
from data.yfinance_loader import YFinanceLoader
from features.feature_engine import FeatureEngine
from regime.regime_engine import RegimeAssessment
from strategies.base_strategy import BaseStrategy
from strategies.momentum import MomentumStrategy


@dataclass
class ChargeModel:
    brokerage_flat: float = 0.0
    brokerage_pct: float = 0.0
    stt_pct: float = 0.1
    exchange_charges_pct: float = 0.00297
    stamp_duty_pct: float = 0.015
    sebi_charges_pct: float = 0.0001

    def buy_charges(self, turnover: float) -> float:
        brokerage = self.brokerage_flat + turnover * (self.brokerage_pct / 100)
        exchange = turnover * (self.exchange_charges_pct / 100)
        stt = turnover * (self.stt_pct / 100)
        stamp = turnover * (self.stamp_duty_pct / 100)
        sebi = turnover * (self.sebi_charges_pct / 100)
        gst = (brokerage + exchange) * 0.18
        return brokerage + stt + exchange + stamp + sebi + gst

    def sell_charges(self, turnover: float) -> float:
        brokerage = self.brokerage_flat + turnover * (self.brokerage_pct / 100)
        exchange = turnover * (self.exchange_charges_pct / 100)
        stt = turnover * (self.stt_pct / 100)
        sebi = turnover * (self.sebi_charges_pct / 100)
        gst = (brokerage + exchange) * 0.18
        return brokerage + stt + exchange + sebi + gst


@dataclass
class TradeRecord:
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    quantity: int
    gross_pnl: float
    charges: float
    net_pnl: float
    exit_reason: str
    entry_regime: str = ""
    symbol: str = ""


@dataclass
class BacktestResult:
    net_pnl: float
    gross_pnl: float
    total_charges: float
    trade_count: int
    trades: list


def _nifty_closes(start: datetime, end: datetime) -> list[float]:
    df = yf.Ticker("^NSEI").history(start=start, end=end)
    df = df.dropna(subset=["Close"])
    return df["Close"].tolist()


def _nifty_series(start: datetime, end: datetime) -> list[tuple]:
    """NIFTY closes paired with their dates, so each stock bar can be matched
    to the NIFTY history up to that exact date (not just the same list index)."""
    df = yf.Ticker("^NSEI").history(start=start, end=end)
    df = df.dropna(subset=["Close"])
    return [(ts.date(), float(c)) for ts, c in zip(df.index, df["Close"])]


@dataclass
class MultiBacktestResult:
    net_pnl: float
    gross_pnl: float
    total_charges: float
    trade_count: int
    trades: list                                   # all symbols, sorted by exit_date
    per_symbol: list = field(default_factory=list)  # [{symbol, trades, net_pnl, win_rate_%}]
    errors: dict = field(default_factory=dict)      # symbol -> error message


def _regime_at(closes_so_far: list[float]) -> RegimeAssessment:
    if len(closes_so_far) < 200:
        return RegimeAssessment(regime=MarketRegime.SIDEWAYS, confidence=0.0, risk_level=RiskLevel.MODERATE)
    price = closes_so_far[-1]
    sma50 = sum(closes_so_far[-50:]) / 50
    sma200 = sum(closes_so_far[-200:]) / 200
    above_50, above_200 = price > sma50, price > sma200
    sma50_above_200 = sma50 > sma200
    if above_50 and above_200 and sma50_above_200:
        regime = MarketRegime.MODERATE_BULL
    elif above_200 and not above_50:
        regime = MarketRegime.WEAK_BULL
    elif above_50 and not above_200:
        regime = MarketRegime.WEAK_BEAR
    elif not sma50_above_200:
        regime = MarketRegime.WEAK_BEAR
    else:
        regime = MarketRegime.SIDEWAYS
    return RegimeAssessment(regime=regime, confidence=0.5, risk_level=RiskLevel.MODERATE)


class BacktestEngine:
    def __init__(self, charge_model: ChargeModel):
        self.charge_model = charge_model

    def run(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        capital: float = 100000.0,
        max_holding_days: int = 10,
        stop_atr_multiplier: float = 2.0,
        risk_pct_per_trade: float = 1.0,
        strategy: BaseStrategy | None = None,
        slippage_pct: float = 0.0,
        nifty_series: list | None = None,
    ) -> BacktestResult:
        loader = YFinanceLoader()
        lookback_start = start_date - timedelta(days=400)
        bars = loader.get_historical_bars(symbol, lookback_start, end_date)
        if nifty_series is None:
            nifty_series = _nifty_series(lookback_start, end_date)
        nifty_dates = [d for d, _ in nifty_series]
        nifty_closes = [c for _, c in nifty_series]

        fe = FeatureEngine()
        if strategy is None:
            strategy = MomentumStrategy()

        trades: list[TradeRecord] = []
        position = None

        start_idx = 0
        for i, b in enumerate(bars):
            if b.timestamp.date() >= start_date.date():
                start_idx = i
                break

        for i in range(start_idx, len(bars)):
            bars_so_far = bars[: i + 1]
            # Date-aligned: NIFTY closes up to and including this bar's date
            # (previously index-aligned, which drifts if a stock has missing days
            # or listed after the lookback start).
            nifty_so_far = nifty_closes[: bisect_right(nifty_dates, bars[i].timestamp.date())]

            if position is None:
                if len(bars_so_far) >= 25:
                    features = fe.compute(symbol, bars_so_far)
                    regime = _regime_at(nifty_so_far)
                    signal = strategy.evaluate(symbol, features, regime)
                    if signal.decision == Decision.BUY and i + 1 < len(bars):
                        entry_bar = bars[i + 1]
                        entry_price = entry_bar.open * (1 + slippage_pct / 100)  # adverse fill: pay more
                        atr_stop_distance = features.atr * stop_atr_multiplier if features.atr else entry_price * 0.03
                        stop_price = entry_price - atr_stop_distance
                        risk_amount = capital * (risk_pct_per_trade / 100)
                        risk_per_share = entry_price - stop_price
                        quantity = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
                        if quantity > 0:
                            position = {
                                "entry_idx": i + 1,
                                "entry_price": entry_price,
                                "stop_price": stop_price,
                                "quantity": quantity,
                                "entry_date": entry_bar.timestamp,
                                "entry_regime": regime.regime.value,
                            }
            else:
                current_bar = bars[i]
                days_held = i - position["entry_idx"]
                exit_reason, exit_price = None, None

                if current_bar.low <= position["stop_price"]:
                    exit_reason, exit_price = "STOP_LOSS", position["stop_price"] * (1 - slippage_pct / 100)
                elif days_held >= max_holding_days:
                    exit_reason, exit_price = "TIME_BASED", current_bar.close * (1 - slippage_pct / 100)

                if exit_reason:
                    buy_turnover = position["entry_price"] * position["quantity"]
                    sell_turnover = exit_price * position["quantity"]
                    charges = (
                        self.charge_model.buy_charges(buy_turnover)
                        + self.charge_model.sell_charges(sell_turnover)
                    )
                    gross_pnl = (exit_price - position["entry_price"]) * position["quantity"]
                    net_pnl = gross_pnl - charges
                    trades.append(
                        TradeRecord(
                            entry_date=position["entry_date"],
                            exit_date=current_bar.timestamp,
                            entry_price=round(position["entry_price"], 2),
                            exit_price=round(exit_price, 2),
                            quantity=position["quantity"],
                            gross_pnl=round(gross_pnl, 2),
                            charges=round(charges, 2),
                            net_pnl=round(net_pnl, 2),
                            exit_reason=exit_reason,
                            entry_regime=position.get("entry_regime", ""),
                            symbol=symbol,
                        )
                    )
                    position = None

        gross_total = sum(t.gross_pnl for t in trades)
        charges_total = sum(t.charges for t in trades)
        net_total = sum(t.net_pnl for t in trades)

        return BacktestResult(
            net_pnl=round(net_total, 2),
            gross_pnl=round(gross_total, 2),
            total_charges=round(charges_total, 2),
            trade_count=len(trades),
            trades=trades,
        )

    def run_multi(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        strategy_factory: Callable[[], BaseStrategy],
        capital: float = 100000.0,
        max_holding_days: int = 10,
        stop_atr_multiplier: float = 2.0,
        risk_pct_per_trade: float = 1.0,
        slippage_pct: float = 0.0,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> MultiBacktestResult:
        """Runs the same single-symbol backtest independently on each symbol and
        pools the trades. Each symbol is sized off the same capital, so this measures
        whether the strategy has an edge across many stocks (bigger sample) — it is
        NOT a shared-capital portfolio simulation (overlapping positions aren't capped).
        A fresh strategy instance is created per symbol so no state leaks between them.
        NIFTY is fetched once and reused for every symbol."""
        lookback_start = start_date - timedelta(days=400)
        nifty_series = _nifty_series(lookback_start, end_date)

        all_trades: list[TradeRecord] = []
        per_symbol: list[dict] = []
        errors: dict[str, str] = {}

        for idx, sym in enumerate(symbols):
            if progress_callback:
                progress_callback(idx, len(symbols), sym)
            try:
                res = self.run(
                    sym, start_date, end_date, capital=capital,
                    max_holding_days=max_holding_days,
                    stop_atr_multiplier=stop_atr_multiplier,
                    risk_pct_per_trade=risk_pct_per_trade,
                    strategy=strategy_factory(),
                    slippage_pct=slippage_pct,
                    nifty_series=nifty_series,
                )
            except Exception as e:  # one bad symbol must not kill the whole run
                errors[sym] = str(e)
                continue
            all_trades.extend(res.trades)
            wins = sum(1 for t in res.trades if t.net_pnl > 0)
            per_symbol.append({
                "symbol": sym,
                "trades": res.trade_count,
                "net_pnl": res.net_pnl,
                "win_rate_%": round(wins / res.trade_count * 100, 1) if res.trade_count else 0.0,
            })

        if progress_callback:
            progress_callback(len(symbols), len(symbols), "")

        all_trades.sort(key=lambda t: t.exit_date)
        return MultiBacktestResult(
            net_pnl=round(sum(t.net_pnl for t in all_trades), 2),
            gross_pnl=round(sum(t.gross_pnl for t in all_trades), 2),
            total_charges=round(sum(t.charges for t in all_trades), 2),
            trade_count=len(all_trades),
            trades=all_trades,
            per_symbol=per_symbol,
            errors=errors,
        )
