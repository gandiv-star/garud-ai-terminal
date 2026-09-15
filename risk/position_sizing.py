from dataclasses import dataclass


@dataclass
class SizingInput:
    available_capital: float
    max_risk_pct: float
    entry_price: float
    stop_price: float
    lot_size: int = 1


def calculate_quantity(sizing_input: SizingInput) -> int:
    risk_per_share = abs(sizing_input.entry_price - sizing_input.stop_price)
    if risk_per_share <= 0:
        return 0

    max_risk_amount = sizing_input.available_capital * (sizing_input.max_risk_pct / 100)
    raw_quantity = max_risk_amount / risk_per_share

    lots = int(raw_quantity // sizing_input.lot_size)
    return max(lots * sizing_input.lot_size, 0)
