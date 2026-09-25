from llm.news_engine import NewsEngine

print("--- Verify: News Engine (yfinance headlines + Gemini summary) ---")
try:
    engine = NewsEngine()
    events = engine.fetch_headlines("RELIANCE", limit=5)
    print(f"Fetched {len(events)} headlines:")
    for e in events:
        print(f"  - [{e.timestamp}] {e.title} ({e.publisher})")

    if events:
        summary = engine.summarize_with_ai("RELIANCE", events)
        print("\nAI summary:")
        print(summary)
    else:
        print("No headlines returned — either yfinance's news feed is empty for this symbol, or the parsing needs adjustment.")
except Exception as e:
    print(f"FAILED: {e}")
