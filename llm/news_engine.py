"""
News Engine (master spec section 15).

Fetches REAL headlines via yfinance's free news feed (no paid API), then
optionally asks Gemini to summarize sentiment — using ONLY the fetched
headlines, never inventing facts. Never trades off a single headline; this
is intelligence/context support, not a trading trigger.

yfinance's news structure changed recently (nested under "content" as of
~2026); this handles both the new nested format and the older flat format
defensively, since we cannot verify which version Streamlit Cloud has
installed without testing live.
"""

from dataclasses import dataclass
from datetime import datetime

import yfinance as yf

from data.yfinance_loader import to_yfinance_symbol
from llm.ai_reasoning import AIReasoningEngine


@dataclass
class MarketEvent:
    symbol: str
    timestamp: datetime | None
    title: str
    publisher: str
    link: str


class NewsEngine:
    def fetch_headlines(self, symbol: str, limit: int = 5) -> list[MarketEvent]:
        ticker = yf.Ticker(to_yfinance_symbol(symbol))
        raw_items = ticker.news or []
        events: list[MarketEvent] = []

        for item in raw_items[:limit]:
            content = item.get("content") if isinstance(item.get("content"), dict) else item

            title = content.get("title") or item.get("title") or ""
            if not title:
                continue

            pub_date_str = content.get("pubDate")
            timestamp = None
            if pub_date_str:
                try:
                    timestamp = datetime.fromisoformat(str(pub_date_str).replace("Z", "+00:00"))
                except Exception:
                    timestamp = None
            elif item.get("providerPublishTime"):
                try:
                    timestamp = datetime.fromtimestamp(item["providerPublishTime"])
                except Exception:
                    timestamp = None

            provider = content.get("provider")
            publisher = provider.get("displayName") if isinstance(provider, dict) else item.get("publisher", "")

            canonical = content.get("canonicalUrl")
            link = canonical.get("url") if isinstance(canonical, dict) else item.get("link", "")

            events.append(
                MarketEvent(symbol=symbol, timestamp=timestamp, title=title, publisher=publisher or "", link=link or "")
            )
        return events

    def summarize_with_ai(self, symbol: str, events: list[MarketEvent]) -> str:
        if not events:
            return "No recent headlines found for this symbol."

        headlines_text = "\n".join(f"- {e.title} ({e.publisher or 'unknown source'})" for e in events)
        prompt = (
            f"Below are the {len(events)} most recent real news headlines for the Indian "
            f"stock {symbol}. Using ONLY these headlines — do not invent any facts, prices, "
            "or events not shown here — write a brief (2-3 sentence), neutral summary of "
            "what they suggest, if anything, about sentiment. If the headlines look like "
            "noise or are unrelated to the company's fundamentals, say so plainly. Do not "
            "give financial advice.\n\n"
            f"{headlines_text}"
        )
        reasoning_engine = AIReasoningEngine()
        return reasoning_engine.generate_text(prompt)
