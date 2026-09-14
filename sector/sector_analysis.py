from dataclasses import dataclass


@dataclass
class SectorStrength:
    sector: str
    sector_return: float
    index_return: float

    @property
    def relative_strength(self) -> float:
        return self.sector_return - self.index_return


class SectorAnalysisEngine:
    def rank_sectors(self, index_symbol: str = "NIFTY") -> list[SectorStrength]:
        raise NotImplementedError
