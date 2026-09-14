from enum import Enum


class TradingMode(str, Enum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    CONTROLLED_LIVE = "CONTROLLED_LIVE"
    LIVE = "LIVE"


class Decision(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


class MarketRegime(str, Enum):
    STRONG_BULL = "STRONG_BULL_TREND"
    MODERATE_BULL = "MODERATE_BULL"
    WEAK_BULL = "WEAK_BULL"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    WEAK_BEAR = "WEAK_BEAR"
    STRONG_BEAR = "STRONG_BEAR_TREND"
    CRISIS = "CRISIS_ABNORMAL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


DEFAULT_UNIVERSE: list[str] = []
