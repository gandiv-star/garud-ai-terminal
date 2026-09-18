from datetime import datetime, timedelta

import yfinance as yf
from dataclasses import dataclass


@dataclass
class CorrelationCheck:
    symbol_a: str
    symbol_b: str
    correlation: float


def _daily_returns(symbol: str, lookback_days: int) -> list[float]:
    end = datetime.now()
    start = end - timedelta(days=lookback_days)
    df = yf.Ticker(f"{symbol}.NS").history(start=start, end=end)
    df = df.dropna(subset=["Close"])
    closes = df["Close"].tolist()
    return [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]


class CorrelationEngine:
    def pairwise_correlation(self, symbol_a: str, symbol_b: str, lookback_days: int = 90) -> CorrelationCheck:
        returns_a = _daily_returns(symbol_a, lookback_days)
        returns_b = _daily_returns(symbol_b, lookback_days)
        n = min(len(returns_a), len(returns_b))
        if n < 5:
            return CorrelationCheck(symbol_a, symbol_b, 0.0)
        a, b = returns_a[-n:], returns_b[-n:]
        mean_a, mean_b = sum(a) / n, sum(b) / n
        cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / n
        std_a = (sum((x - mean_a) ** 2 for x in a) / n) ** 0.5
        std_b = (sum((x - mean_b) ** 2 for x in b) / n) ** 0.5
        if std_a == 0 or std_b == 0:
            return CorrelationCheck(symbol_a, symbol_b, 0.0)
        return CorrelationCheck(symbol_a, symbol_b, round(cov / (std_a * std_b), 4))

    def max_correlation_with_open_positions(self, symbol: str, open_symbols: list[str]) -> float:
        if not open_symbols:
            return 0.0
        correlations = [self.pairwise_correlation(symbol, s).correlation for s in open_symbols]
        return max(correlations) if correlations else 0.0
