from dataclasses import dataclass


@dataclass
class ChargeModel:
    brokerage_flat: float = 0.0
    brokerage_pct: float = 0.0
    stt_pct: float = 0.0
    exchange_charges_pct: float = 0.0
    gst_pct: float = 0.0
    stamp_duty_pct: float = 0.0
    sebi_charges_pct: float = 0.0

    def total_charge(self, turnover: float) -> float:
        pct_total = (
            self.brokerage_pct
            + self.stt_pct
            + self.exchange_charges_pct
            + self.gst_pct
            + self.stamp_duty_pct
            + self.sebi_charges_pct
        )
        return self.brokerage_flat + turnover * (pct_total / 100)


@dataclass
class BacktestResult:
    net_pnl: float
    gross_pnl: float
    total_charges: float
    trade_count: int


class BacktestEngine:
    def __init__(self, charge_model: ChargeModel):
        self.charge_model = charge_model

    def run(self, strategy, start_date, end_date) -> BacktestResult:
        raise NotImplementedError
