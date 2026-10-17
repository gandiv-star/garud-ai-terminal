"""AI advisory layer — Gemini explains a scanner candidate; it never decides.

Rules (Master Command, Phase 5):
  * input = only facts Garud already computed (rule checks, prices, regime, backtest and paper
    stats, risk numbers) — the prompt forbids new numbers, predictions and buy/sell advice;
  * the rules and the risk limits stay the only decision makers; nothing here places orders;
  * every answer is stored as an AI_ADVICE audit event with model, prompt version, input facts,
    output and timestamps; failures are shown as "AI unavailable" and never stored as advice.
"""
import json
import time
from datetime import datetime, timezone

PROMPT_VERSION = "advisor_v1"


def model_name() -> str:
    try:
        from llm.ai_reasoning import GEMINI_URL
        return GEMINI_URL.rsplit("/models/", 1)[-1].split(":")[0]
    except Exception:
        return "gemini"


def build_facts(row: dict, mode: dict | None, bench: dict | None, paper: dict | None,
                sector: str, sector_open: int) -> dict:
    ctx = (mode or {}).get("context") or {}
    return {
        "symbol": row.get("symbol"), "data_date": row.get("date"), "last_close": row.get("close"),
        "scanner_action": row.get("action"), "scanner_reason": row.get("reason"),
        "rule_checks": row.get("checks"), "reference_levels": row.get("ref"),
        "pct_vs_sma20": row.get("trend_pct"), "return_10d_pct": row.get("mom10_pct"),
        "atr_pct_of_price": row.get("atr_pct"), "relative_volume": row.get("rel_volume"),
        "nifty_regime": (mode or {}).get("regime"), "trading_mode": (mode or {}).get("mode"),
        "nifty_vs_sma50_pct": ctx.get("vs_sma50_pct"), "nifty_vs_sma200_pct": ctx.get("vs_sma200_pct"),
        "nifty_vol_percentile": ctx.get("vol_percentile"),
        "rule_backtest_5y": bench, "rule_paper_so_far": paper,
        "sector": sector, "open_paper_positions_in_sector": sector_open,
    }


def build_prompt(facts: dict) -> str:
    return (
        "You are the explanation layer of Garud, a rule-based paper-trading system for NSE stocks.\n"
        "The rules have ALREADY decided. You must NOT change, recommend or predict anything.\n"
        "Use ONLY the JSON facts below; do not invent any number, news, target or probability.\n"
        "Write in simple Gujarati (technical words may stay in English), at most 8 short bullet points:\n"
        "1) why the rule flagged this stock (cite the facts), 2) supporting evidence, "
        "3) conflicting signals or reasons for caution, 4) what invalidates it (the stop level), "
        "5) the evidence status of the rule (backtest vs paper, still unproven if fewer than 30 paper trades), "
        "6) any missing or weak data.\n"
        "End with exactly this line: 'આ માત્ર સમજૂતી છે — નિર્ણય Garud ના નિયમો અને risk મર્યાદાઓ જ લે છે.'\n\n"
        "FACTS:\n" + json.dumps(facts, ensure_ascii=False, default=str)
    )


def unavailable(text: str) -> bool:
    return (not text) or text.strip().startswith("(AI reasoning unavailable")


TRANSIENT = ("503", "429", "500", "502", "504", "overloaded", "unavailable", "timed out", "timeout")


def friendly_error(text: str) -> str:
    t = (text or "").lower()
    if "503" in t or "overloaded" in t:
        return "Gemini અત્યારે વ્યસ્ત છે (503) — થોડી મિનિટ પછી ફરી દબાવો"
    if "429" in t or "quota" in t:
        return "Gemini નો quota પૂરો થયો (429) — થોડી વાર પછી ફરી દબાવો"
    if "key" in t and ("configured" in t or "invalid" in t or "401" in t or "403" in t):
        return "Gemini key ની તકલીફ — Health tab માં ચકાસો"
    return "Gemini જવાબ ન મળ્યો — થોડી વાર પછી ફરી દબાવો"


def advise(facts: dict, call_fn, now: datetime | None = None, retries: int = 2, wait=time.sleep) -> dict:
    """call_fn(prompt) -> text. Transient errors (503/429/timeouts) are retried with backoff.
    Returns the record (ok=False when the AI is unavailable)."""
    now = now or datetime.now(timezone.utc)
    prompt = build_prompt(facts)
    text = call_fn(prompt)
    for attempt in range(retries):
        if not unavailable(text) or not any(k in text.lower() for k in TRANSIENT):
            break
        wait(2 * (attempt + 1))
        text = call_fn(prompt)
    return {"ok": not unavailable(text), "symbol": facts.get("symbol"), "data_date": facts.get("data_date"),
            "model": model_name(), "prompt_version": PROMPT_VERSION, "input": facts, "output": text,
            "created_at": now.isoformat(timespec="seconds"),
            "error": friendly_error(text) if unavailable(text) else None}


def cached(db, symbol: str, data_date: str) -> dict | None:
    for ev in db.get_audit_events("AI_ADVICE", limit=300):
        p = ev.payload or {}
        if p.get("symbol") == symbol and p.get("data_date") == data_date and p.get("prompt_version") == PROMPT_VERSION:
            return p
    return None


def save(db, record: dict) -> None:
    from database.models import AuditEvent
    db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type="AI_ADVICE",
                                   symbol=record.get("symbol"),
                                   payload=json.loads(json.dumps(record, ensure_ascii=False, default=str))))
