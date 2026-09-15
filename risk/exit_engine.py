from dataclasses import dataclass
from enum import Enum


class ExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TARGET = "TARGET"
    TRAILING_STOP = "TRAILING_STOP"
    TREND_DETERIORATION = "TREND_DETERIORATION"
    SIGNAL_REVERSAL = "SIGNAL_REVERSAL"
    REGIME_CHANGE = "REGIME_CHANGE"
    TIME_BASED = "TIME_BASED"
    VOLATILITY_CHANGE = "VOLATILITY_CHANGE"
    MODEL_DETERIORATION = "MODEL_DETERIORATION"
    RISK_LIMIT = "RISK_LIMIT"


@dataclass
class ExitSignal:
    symbol: str
    reason: ExitReason
    should_exit: bool


class ExitEngine:
    def check(self, symbol: str) -> ExitSignal:
        raise NotImplementedError
