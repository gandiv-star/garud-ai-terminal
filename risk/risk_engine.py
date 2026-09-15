from dataclasses import dataclass, field

from config.settings import RiskLimits


@dataclass
class RiskVerdict:
    approved: bool
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class TradeProposal:
    symbol: str
    quantity: int
    entry_price: float
    stop_price: float
    sector: str


class RiskEngine:
    def __init__(self, limits: RiskLimits):
        self.limits = limits

    def evaluate(
        self,
        proposal: TradeProposal,
        available_capital: float,
        current_daily_pnl_pct: float,
        current_portfolio_drawdown_pct: float,
        current_sector_exposure_pct: float,
        open_position_count: int,
    ) -> RiskVerdict:
        reasons: list[str] = []

        if current_daily_pnl_pct <= -abs(self.limits.max_daily_loss_pct):
            reasons.append("daily_loss_limit_breached")
        if current_portfolio_drawdown_pct >= self.limits.max_portfolio_drawdown_pct:
            reasons.append("portfolio_drawdown_limit_breached")
        if open_position_count >= self.limits.max_open_positions:
            reasons.append("max_open_positions_reached")
        if current_sector_exposure_pct >= self.limits.max_sector_exposure_pct:
            reasons.append("sector_exposure_limit_breached")

        risk_amount = abs(proposal.entry_price - proposal.stop_price) * proposal.quantity
        max_risk_amount = available_capital * (self.limits.max_risk_per_trade_pct / 100)
        if risk_amount > max_risk_amount:
            reasons.append("per_trade_risk_exceeds_limit")

        return RiskVerdict(approved=len(reasons) == 0, rejection_reasons=reasons)
