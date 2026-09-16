from dataclasses import dataclass, field

import yfinance as yf

from core.constants import MarketRegime, RiskLevel

NIFTY_YFINANCE_TICKER = "^NSEI"


@dataclass
class RegimeAssessment:
    regime: MarketRegime
    confidence: float
    supporting_features: dict[str, float] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.MODERATE


class RegimeEngine:
    def detect(self, index_symbol: str = "NIFTY") -> RegimeAssessment:
        ticker = yf.Ticker(NIFTY_YFINANCE_TICKER)
        df = ticker.history(period="1y")
        df = df.dropna(subset=["Close"])

        if len(df) < 200:
            return RegimeAssessment(
                regime=MarketRegime.SIDEWAYS,
                confidence=0.0,
                supporting_features={"bars_available": float(len(df))},
                risk_level=RiskLevel.MODERATE,
            )

        close = df["Close"]
        price = float(close.iloc[-1])
        sma50 = float(close.rolling(50).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1])

        daily_returns = close.pct_change().dropna()
        volatility_20d = float(daily_returns.tail(20).std() * (252 ** 0.5))

        features = {
            "price": price,
            "sma50": sma50,
            "sma200": sma200,
            "volatility_20d_annualized": volatility_20d,
            "price_vs_sma50_pct": (price - sma50) / sma50 * 100,
            "price_vs_sma200_pct": (price - sma200) / sma200 * 100,
        }

        if volatility_20d > 0.35:
            return RegimeAssessment(
                regime=MarketRegime.CRISIS, confidence=0.6,
                supporting_features=features, risk_level=RiskLevel.CRITICAL,
            )
        if volatility_20d > 0.22:
            return RegimeAssessment(
                regime=MarketRegime.HIGH_VOLATILITY, confidence=0.6,
                supporting_features=features, risk_level=RiskLevel.HIGH,
            )

        above_50 = price > sma50
        above_200 = price > sma200
        sma50_above_200 = sma50 > sma200

        if above_50 and above_200 and sma50_above_200:
            regime = MarketRegime.STRONG_BULL if features["price_vs_sma200_pct"] > 8 else MarketRegime.MODERATE_BULL
            risk = RiskLevel.LOW
        elif above_200 and not above_50:
            regime = MarketRegime.WEAK_BULL
            risk = RiskLevel.MODERATE
        elif not above_200 and above_50:
            regime = MarketRegime.WEAK_BEAR
            risk = RiskLevel.MODERATE
        elif not above_50 and not above_200 and not sma50_above_200:
            regime = MarketRegime.STRONG_BEAR if features["price_vs_sma200_pct"] < -8 else MarketRegime.WEAK_BEAR
            risk = RiskLevel.HIGH
        else:
            regime = MarketRegime.SIDEWAYS
            risk = RiskLevel.MODERATE

        confidence = min(abs(features["price_vs_sma200_pct"]) / 10, 1.0)

        return RegimeAssessment(
            regime=regime,
            confidence=round(confidence, 2),
            supporting_features={k: round(v, 4) for k, v in features.items()},
            risk_level=risk,
        )
