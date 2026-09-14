import os
from dataclasses import dataclass, field

from core.constants import TradingMode


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val is not None else default


@dataclass
class RiskLimits:
    max_risk_per_trade_pct: float = field(
        default_factory=lambda: _env_float("MAX_RISK_PER_TRADE_PCT", 1.0)
    )
    max_daily_loss_pct: float = field(
        default_factory=lambda: _env_float("MAX_DAILY_LOSS_PCT", 3.0)
    )
    max_portfolio_drawdown_pct: float = field(
        default_factory=lambda: _env_float("MAX_PORTFOLIO_DRAWDOWN_PCT", 10.0)
    )
    max_open_positions: int = field(
        default_factory=lambda: int(os.getenv("MAX_OPEN_POSITIONS", 10))
    )
    max_sector_exposure_pct: float = field(
        default_factory=lambda: _env_float("MAX_SECTOR_EXPOSURE_PCT", 30.0)
    )


@dataclass
class Settings:
    trading_mode: TradingMode = field(
        default_factory=lambda: TradingMode(os.getenv("TRADING_MODE", "BACKTEST"))
    )
    broker_name: str = field(default_factory=lambda: os.getenv("BROKER_NAME", ""))
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///garud.db")
    )
    kill_switch_enabled: bool = field(
        default_factory=lambda: _env_bool("KILL_SWITCH_ENABLED", True)
    )
    risk: RiskLimits = field(default_factory=RiskLimits)

    def require_explicit_live(self) -> None:
        if self.trading_mode not in (TradingMode.CONTROLLED_LIVE, TradingMode.LIVE):
            raise RuntimeError("Refusing live action: not a live-capable mode.")
        if not self.kill_switch_enabled:
            raise RuntimeError("Refusing live action: kill switch is disabled.")


def load_settings() -> Settings:
    return Settings()
