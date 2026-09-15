from dataclasses import dataclass
from enum import Enum


class StopMethod(str, Enum):
    ATR = "ATR"
    VOLATILITY_ADJUSTED = "VOLATILITY_ADJUSTED"
    STRUCTURE_BASED = "STRUCTURE_BASED"
    STRATEGY_SPECIFIC = "STRATEGY_SPECIFIC"


@dataclass
class StopLossResult:
    stop_price: float
    method: StopMethod


def calculate_atr_stop(entry_price: float, atr: float, multiplier: float = 2.0) -> StopLossResult:
    return StopLossResult(stop_price=entry_price - (atr * multiplier), method=StopMethod.ATR)
