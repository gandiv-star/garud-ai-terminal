from dataclasses import dataclass
from datetime import datetime, timedelta

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
    ) -> BacktestResult:
        loader = YFinanceLoader()
        lookback_start = start_date - timedelta(days=400)
        bars = loader.get_historical_bars(symbol, lookback_start, end_date)
        nifty_closes = _nifty_closes(lookback_start, end_date)

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
            nifty_so_far = nifty_closes[: i + 1] if i < len(nifty_closes) else nifty_closes

            if position is None:
                if len(bars_so_far) >= 25:
                    features = fe.compute(symbol, bars_so_far)
                    regime = _regime_at(nifty_so_far)
                    signal = strategy.evaluate(symbol, features, regime)
                    if signal.decision == Decision.BUY and i + 1 < len(bars):
                        entry_bar = bars[i + 1]
                        entry_price = entry_bar.open
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
                            }
            else:
                current_bar = bars[i]
                days_held = i - position["entry_idx"]
                exit_reason, exit_price = None, None

                if current_bar.low <= position["stop_price"]:
                    exit_reason, exit_price = "STOP_LOSS", position["stop_price"]
                elif days_held >= max_holding_days:
                    exit_reason, exit_price = "TIME_BASED", current_bar.close

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
