"""Pre-trade checks for LIVE equity orders (#47 margin, #117 tick size / quantity, #118 cash).

Only the live path uses these (live trading is OFF); paper trading is not affected.
Tick sizes: NSE cash market, effective 15 Apr 2025 (NSE circular, summarised by brokers, checked
22 Oct 2026). NSE assigns the band from the previous month's closing price, so near a band edge the
reference price can pick the neighbouring band: round_to_tick() therefore rounds to a multiple of the
LARGER of the two neighbouring ticks when the price is within 2% of a band edge.
"""
import math

# (upper price limit, tick) — price <= limit uses that tick
TICK_BANDS = ((250.0, 0.01), (1000.0, 0.05), (5000.0, 0.10), (10000.0, 0.50), (20000.0, 1.00), (math.inf, 5.00))
EDGE_PCT = 2.0
CASH_BUFFER_PCT = 1.0        # keep 1% of the order value spare for charges and price moves


def tick_size(price: float) -> float:
    for limit, tick in TICK_BANDS:
        if price <= limit:
            return tick
    return TICK_BANDS[-1][1]


def safe_tick(price: float) -> float:
    """Tick to align to: near a band edge use the bigger neighbouring tick (valid in both bands,
    because every bigger tick is a whole multiple of the smaller ones)."""
    lo, hi = price * (1 - EDGE_PCT / 100), price * (1 + EDGE_PCT / 100)
    return max(tick_size(lo), tick_size(price), tick_size(hi))


def round_to_tick(price: float, direction: str = "nearest") -> float:
    """direction: 'up', 'down' or 'nearest'. A protective SELL stop trigger is rounded UP
    (closer to the market = exits a little earlier, never later)."""
    if not price or price <= 0:
        raise ValueError(f"invalid price {price}")
    t = safe_tick(price)
    n = price / t
    n = math.ceil(n - 1e-9) if direction == "up" else math.floor(n + 1e-9) if direction == "down" else round(n)
    return round(n * t, 2)


def on_tick(price: float) -> bool:
    t = tick_size(price)
    return abs(price / t - round(price / t)) < 1e-6


def quantity_problem(qty) -> str | None:
    if isinstance(qty, bool) or not isinstance(qty, int):
        return f"quantity {qty!r} is not a whole number"
    if qty <= 0:
        return f"quantity {qty} must be at least 1"
    return None


def available_margin(funds) -> float | None:
    """Equity cash available to trade from an Upstox funds-and-margin response
    ({"data": {"equity": {"available_margin": ...}}}). None when it cannot be read (fail closed)."""
    try:
        data = funds.get("data", funds) if isinstance(funds, dict) else None
        eq = (data or {}).get("equity") or {}
        v = float(eq.get("available_margin"))
        return v if math.isfinite(v) and v >= 0 else None
    except (TypeError, ValueError, AttributeError):
        return None


def affordable_qty(qty: int, price: float, available: float | None, buy_charges) -> tuple[int, str]:
    """(qty that fits the available cash, reason). buy_charges(value) -> rupees.
    Unknown cash -> 0 (fail closed)."""
    if available is None:
        return 0, "available cash unknown — BUY blocked (fail closed)"
    if price <= 0 or qty <= 0:
        return 0, "nothing to buy"
    q = qty
    while q > 0 and q * price * (1 + CASH_BUFFER_PCT / 100) + buy_charges(q * price) > available:
        q -= 1
    if q <= 0:
        return 0, f"not enough cash (available Rs.{available:,.0f})"
    if q < qty:
        return q, f"reduced {qty}→{q} to fit available cash Rs.{available:,.0f}"
    return q, ""
