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


def _returns_from_close(close_series) -> float:
    close_series = close_series.dropna()
    if len(close_series) < 2:
        return None
    start_price = float(close_series.iloc[0])
    end_price = float(close_series.iloc[-1])
    return (end_price - start_price) / start_price * 100


class SectorAnalysisEngine:
    def rank_sectors(self, index_symbol: str = "NIFTY", period: str = "1mo") -> list[SectorStrength]:
        all_tickers = [INDEX_TICKER] + list(SECTOR_TICKERS.values())
        data = yf.download(all_tickers, period=period, group_by="ticker", progress=False)

        index_return = _returns_from_close(data[INDEX_TICKER]["Close"])
        if index_return is None:
            raise RuntimeError(f"Could not fetch index data for {INDEX_TICKER}")

        results: list[SectorStrength] = []
        skipped: list[str] = []
        for sector_name, ticker in SECTOR_TICKERS.items():
            sector_return = _returns_from_close(data[ticker]["Close"])
            if sector_return is None:
                skipped.append(sector_name)
                continue
            results.append(
                SectorStrength(
                    sector=sector_name,
                    sector_return=round(sector_return, 2),
                    index_return=round(index_return, 2),
                )
            )

        if skipped:
            import streamlit as st
            st.warning(f"Skipped sectors with no data: {skipped}")

        results.sort(key=lambda s: s.relative_strength, reverse=True)
        return results
