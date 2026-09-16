from dataclasses import dataclass

import yfinance as yf

INDEX_TICKER = "^NSEI"

SECTOR_TICKERS = {
    "Banking": "^NSEBANK",
    "IT": "^CNXIT",
    "Pharma": "^CNXPHARMA",
    "Auto": "^CNXAUTO",
    "Metal": "^CNXMETAL",
    "FMCG": "^CNXFMCG",
    "Energy": "^CNXENERGY",
    "Realty": "^CNXREALTY",
}


@dataclass
class SectorStrength:
    sector: str
    sector_return: float
    index_return: float

    @property
    def relative_strength(self) -> float:
        return self.sector_return - self.index_return


def _period_return(ticker: str, period: str = "1mo") -> float:
    df = yf.Ticker(ticker).history(period=period)
    df = df.dropna(subset=["Close"])
    if len(df) < 2:
        return 0.0
    start_price = float(df["Close"].iloc[0])
    end_price = float(df["Close"].iloc[-1])
    return (end_price - start_price) / start_price * 100


class SectorAnalysisEngine:
    def rank_sectors(self, index_symbol: str = "NIFTY", period: str = "1mo") -> list[SectorStrength]:
        index_return = _period_return(INDEX_TICKER, period)

        results: list[SectorStrength] = []
        for sector_name, ticker in SECTOR_TICKERS.items():
            sector_return = _period_return(ticker, period)
            results.append(
                SectorStrength(
                    sector=sector_name,
                    sector_return=round(sector_return, 2),
                    index_return=round(index_return, 2),
                )
            )

        results.sort(key=lambda s: s.relative_strength, reverse=True)
        return results
