from dataclasses import dataclass

import yfinance as yf

SECTOR_STOCKS = {
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN"],
    "IT": ["TCS", "INFY", "WIPRO"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA"],
    "Auto": ["MARUTI", "BAJAJ-AUTO"],
    "Metal": ["TATASTEEL", "HINDALCO", "JSWSTEEL"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND"],
    "Energy": ["RELIANCE", "ONGC", "NTPC"],
    "Realty": ["DLF", "GODREJPROP", "OBEROIRLTY"],
}

INDEX_TICKER = "^NSEI"


@dataclass
class SectorStrength:
    sector: str
    sector_return: float
    index_return: float

    @property
    def relative_strength(self) -> float:
        return self.sector_return - self.index_return


def _period_return(ticker: str, period: str = "1mo") -> float | None:
    df = yf.Ticker(ticker).history(period=period)
    df = df.dropna(subset=["Close"])
    if len(df) < 2:
        return None
    start_price = float(df["Close"].iloc[0])
    end_price = float(df["Close"].iloc[-1])
    return (end_price - start_price) / start_price * 100


class SectorAnalysisEngine:
    def rank_sectors(self, index_symbol: str = "NIFTY", period: str = "1mo") -> list[SectorStrength]:
        index_return = _period_return(INDEX_TICKER, period)
        if index_return is None:
            raise RuntimeError("Could not fetch NIFTY index data")

        results: list[SectorStrength] = []
        for sector_name, stocks in SECTOR_STOCKS.items():
            stock_returns = []
            for stock in stocks:
                ret = _period_return(f"{stock}.NS", period)
                if ret is not None:
                    stock_returns.append(ret)
            if not stock_returns:
                continue
            avg_return = sum(stock_returns) / len(stock_returns)
            results.append(
                SectorStrength(
                    sector=sector_name,
                    sector_return=round(avg_return, 2),
                    index_return=round(index_return, 2),
                )
            )

        results.sort(key=lambda s: s.relative_strength, reverse=True)
        return results
