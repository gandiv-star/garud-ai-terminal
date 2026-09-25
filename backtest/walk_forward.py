"""
Walk-Forward Validation.

Rolls non-overlapping windows forward through history to check whether
strategy performance is stable across different, sequential market
periods — rather than trusting a single in-sample backtest that could
just be luck from one particular stretch of history.

Garud's strategies are fixed-threshold rules, not parameter-fitted
models — there is nothing to "train" or "validate" against. So
train_days/validation_days exist as window-boundary fields for a
future parameter-fitted model, but today only the out-of-sample (OOS)
segment of each window is actually backtested. This is stated plainly
rather than pretending a fit step happens when it doesn't.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class WalkForwardWindow:
    train_start: datetime
    train_end: datetime
    validation_end: datetime
    out_of_sample_end: datetime


class WalkForwardValidator:
    def generate_windows(
        self,
        start_date: datetime,
        end_date: datetime,
        oos_days: int,
        train_days: int = 0,
        validation_days: int = 0,
    ) -> list[WalkForwardWindow]:
        windows: list[WalkForwardWindow] = []
        cursor = start_date
        while True:
            train_start = cursor
            train_end = train_start + timedelta(days=train_days)
            validation_end = train_end + timedelta(days=validation_days)
            oos_end = validation_end + timedelta(days=oos_days)
            if oos_end > end_date:
                break
            windows.append(WalkForwardWindow(train_start, train_end, validation_end, oos_end))
            cursor = oos_end  # non-overlapping: next window starts where this OOS ended
        return windows

    def run(self, symbol: str, strategy, backtest_engine, windows: list[WalkForwardWindow], capital: float = 100000.0) -> list[dict]:
        results: list[dict] = []
        for w in windows:
            result = backtest_engine.run(
                symbol, w.validation_end, w.out_of_sample_end, capital=capital, strategy=strategy
            )
            results.append({
                "window_start": w.validation_end,
                "window_end": w.out_of_sample_end,
                "trades": result.trade_count,
                "net_pnl": result.net_pnl,
            })
        return results
