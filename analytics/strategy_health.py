from dataclasses import dataclass


@dataclass
class StrategyHealth:
    strategy_name: str
    is_degrading: bool
    recent_win_rate: float
    historical_win_rate: float
    notes: str = ""


def _get(trade, key):
    return trade[key] if isinstance(trade, dict) else getattr(trade, key)


class StrategyHealthMonitor:
    def assess(self, strategy_name: str, trades: list, min_trades: int = 10, degradation_threshold_pp: float = 0.15) -> StrategyHealth:
        if len(trades) < min_trades:
            return StrategyHealth(
                strategy_name=strategy_name, is_degrading=False,
                recent_win_rate=0.0, historical_win_rate=0.0,
                notes=f"Not enough trades to assess health (have {len(trades)}, need at least {min_trades}).",
            )

        sorted_trades = sorted(trades, key=lambda t: _get(t, "exit_date"))
        mid = len(sorted_trades) // 2
        historical, recent = sorted_trades[:mid], sorted_trades[mid:]

        def win_rate(ts):
            pnls = [_get(t, "net_pnl") for t in ts]
            wins = sum(1 for p in pnls if p > 0)
            return wins / len(ts) if ts else 0.0

        hist_wr, rec_wr = win_rate(historical), win_rate(recent)
        is_degrading = rec_wr < hist_wr - degradation_threshold_pp
        notes = (
            "Recent performance notably weaker than historical — flag for review, do not auto-disable."
            if is_degrading else "No clear degradation detected."
        )
        return StrategyHealth(
            strategy_name=strategy_name, is_degrading=is_degrading,
            recent_win_rate=round(rec_wr, 3), historical_win_rate=round(hist_wr, 3), notes=notes,
        )
