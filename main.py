from llm.ai_reasoning import AIReasoningEngine

print("--- Verify: AI Reasoning Engine (Gemini) ---")
try:
    engine = AIReasoningEngine()
    result = engine.explain_market_context(
        symbol="RELIANCE",
        regime="WEAK_BEAR",
        regime_confidence=0.51,
        risk_level="HIGH",
        ai_score=50.0,
        strategy_summary="0 of 7 strategies voted BUY; all NO_TRADE.",
        risk_verdict_summary="APPROVED (no hard limits breached).",
    )
    print("Result:")
    print(result)
except Exception as e:
    print(f"FAILED: {e}")
