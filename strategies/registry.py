"""
Strategy Registry (Final Master Command's COMMAND 7).

Central place strategies are listed, so adding a new strategy means
adding ONE line here instead of updating every place strategies are
used throughout the app (Analysis tab, Scanner tab, Backtest dropdown,
Research Lab). Existing strategy files are untouched by this — this
module only imports and lists them.
"""

from strategies.breakout import BreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.regime_adaptive import RegimeAdaptiveStrategy
from strategies.relative_strength import RelativeStrengthStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.volatility_expansion import VolatilityExpansionStrategy
from strategies.volume_breakout import VolumeBreakoutStrategy

# Display name -> strategy class. This order is what dropdowns and the
# "run every strategy" lists (Analysis tab, Scanner tab) use.
STRATEGY_REGISTRY = {
    "Momentum": MomentumStrategy,
    "Breakout": BreakoutStrategy,
    "Trend Following": TrendFollowingStrategy,
    "Mean Reversion": MeanReversionStrategy,
    "Relative Strength": RelativeStrengthStrategy,
    "Volume Breakout": VolumeBreakoutStrategy,
    "Volatility Expansion": VolatilityExpansionStrategy,
    "Regime Adaptive": RegimeAdaptiveStrategy,
}


def all_strategy_instances() -> list:
    """A fresh instance of every registered strategy, in registry order."""
    return [cls() for cls in STRATEGY_REGISTRY.values()]


def strategy_names() -> list[str]:
    return list(STRATEGY_REGISTRY.keys())
