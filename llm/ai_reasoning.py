"""
AI Reasoning Engine — Gemini-powered market-context narrative.

STRICT RULES (per project safety principles):
- Used ONLY for human-readable narrative/explanation, NEVER to make or
  change a trade decision. The Risk Engine and strategy signals remain
  the sole source of truth for BUY/SELL/NO_TRADE.
- The prompt sends Gemini only REAL, already-computed numbers (regime,
  score, signals, risk verdict) and explicitly instructs it not to
  invent any figures.
- Any failure (network, rate limit, API instability) is caught and
  returns a clear fallback message — it must never break the rest of
  the app, since this is an enhancement layer, not a critical path.
"""

import requests

from security.secrets_manager import SecretsManager

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"


class AIReasoningEngine:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or SecretsManager.get("GEMINI_API_KEY", required=False)

    def _call_gemini(self, prompt: str) -> str:
        if not self.api_key:
            return "(AI reasoning unavailable: no GEMINI_API_KEY configured.)"

        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            return f"(AI reasoning unavailable: {e})"

    def explain_market_context(
        self,
        symbol: str,
        regime: str,
        regime_confidence: float,
        risk_level: str,
        ai_score: float,
        strategy_summary: str,
        risk_verdict_summary: str,
    ) -> str:
        prompt = (
            "You are a market-context narrator for a personal Indian equity trading "
            "dashboard. Using ONLY the exact data given below, write a short (3-4 "
            "sentence), plain-language summary of the current situation for this "
            "symbol. Do NOT invent any numbers, prices, or facts not given below. "
            "Do NOT give financial advice or promise any outcome. If the data below "
            "suggests caution, say so plainly.\n\n"
            f"Symbol: {symbol}\n"
            f"Market regime: {regime} (confidence: {regime_confidence})\n"
            f"Risk level: {risk_level}\n"
            f"Composite AI score: {ai_score}/100\n"
            f"Strategy signals summary: {strategy_summary}\n"
            f"Risk Engine verdict: {risk_verdict_summary}\n"
        )
        return self._call_gemini(prompt)
