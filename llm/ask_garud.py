""""Garud ને પૂછો" — a question box that answers in Gujarati from Garud's own numbers.

Rules (same spirit as llm/advisor.py):
  * the AI sees ONLY facts Garud already computed (paper trades, momentum portfolios, options,
    today's mode, market backdrop, study results, health) — it must not invent numbers;
  * it never places, changes or recommends orders, stops or position sizes, and makes no price
    predictions; the paper rules and risk limits stay the only decision makers;
  * every answer is stored as an ASK_GARUD audit event (question, answer, model, prompt version,
    the facts it saw); failures show "AI unavailable" and are not stored as answers;
  * at most MAX_PER_DAY questions per day (the app link is public; this protects the Gemini quota).
"""
import json
from datetime import datetime, timedelta, timezone

from llm import advisor

PROMPT_VERSION = "ask_v2"
EVENT = "ASK_GARUD"
MAX_QUESTION_CHARS = 500
MAX_PER_DAY = 30
MAX_CONTEXT_CHARS = 30000
IST = timezone(timedelta(hours=5, minutes=30))

STANDING_FACTS = {
    "money": "Everything is PAPER trading (no real money). Live orders are disabled until a strategy passes its paper test.",
    "pass_bar_long_term": "15-year CAGR > 7% (FD) AND max drawdown <= 25%",
    "pass_bar_swing_rules": "after 30 closed paper trades: net > 0, PF >= 1.15, not far below backtest",
    "momentum_decision": "M2/G paper portfolios start with the 30 Oct 2026 month-end; decision about small real money in Feb 2027, by the owner",
    "trading_mode_engine": ("YES, Garud changes which paper rules may open NEW trades according to the NIFTY regime "
                            "(the daily 'trading mode', see today_mode: e.g. WEAK_BEAR -> v1/v2 volatility-expansion rules allowed, "
                            "MODERATE_BULL -> v3 trend rule allowed, NO TRADE when nothing fits; the options condor ignores the regime). "
                            "This switch was fixed in advance; the 8 Oct 2026 evidence matrix found NO proof that choosing rules by "
                            "regime improves results, so it is kept only as a pre-registered paper experiment."),
    "rejected_by_tests": "intraday (costs), frequent swing trading (15-year test failed), ML stock picker (worse than the M2 rule)",
    "weak_market_rule": "momentum portfolios move to a liquid fund when NIFTY is weak (validated: weak-market trades lost money in every swing variant)",
    "tax_assumption": "owner's income up to Rs.12 lakh: FD/liquid fund effectively tax-free; shares STCG 20%, LTCG 12.5% above Rs.1.25L",
}


def _trim(obj, limit: int = MAX_CONTEXT_CHARS):
    text = json.dumps(obj, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return obj
    return {"note": "context shortened", "json": text[:limit]}


def build_context(mode=None, rules=None, options=None, momentum=None, studies=None, macro=None,
                  health=None, now: datetime | None = None) -> dict:
    now = now or datetime.now(IST)
    ctx = {"as_of_ist": now.strftime("%Y-%m-%d %H:%M"), "standing_facts": STANDING_FACTS,
           "today_mode": mode, "swing_paper_rules": rules, "options_condor_paper": options,
           "momentum_paper_portfolios": momentum, "completed_studies": studies,
           "market_backdrop": macro, "system_health": health}
    return _trim({k: v for k, v in ctx.items() if v not in (None, [], {})})


def build_prompt(question: str, context: dict, history: list | None = None) -> str:
    past = ""
    for q, a in (history or [])[-3:]:
        past += f"Q: {q}\nA: {a[:800]}\n"
    return (
        "You are 'Garud', the question-answering layer of a rule-based PAPER-trading research system for NSE.\n"
        "Answer the owner's question in simple Gujarati (technical words may stay in English), at most 10 short lines.\n"
        "STRICT RULES:\n"
        "1) Use ONLY the JSON facts below for anything about Garud, its trades, portfolios, results or the market today. "
        "Quote the numbers exactly. If the facts do not contain the answer, say 'Garud પાસે આ માહિતી નથી' and say which screen may help.\n"
        "2) Do NOT recommend buying, selling, changing a stop-loss, position size or any rule; do NOT predict prices or returns. "
        "If asked, explain what Garud's pre-registered rule does and that the rules decide.\n"
        "3) General concepts (e.g. what VIX or drawdown means) may be explained briefly from general knowledge; mark them 'સામાન્ય માહિતી'.\n"
        "4) Never claim a strategy is profitable unless its paper test PASSED in the facts; backtests are past results only.\n"
        "End with exactly this line: 'માત્ર માહિતી — નિર્ણય Garud ના નિયમો અને તમે જ લો છો.'\n\n"
        + (f"EARLIER IN THIS CHAT:\n{past}\n" if past else "")
        + "FACTS:\n" + json.dumps(context, ensure_ascii=False, default=str)
        + f"\n\nQUESTION: {question}"
    )


def clean_question(q: str) -> str:
    return " ".join((q or "").split())[:MAX_QUESTION_CHARS]


def ask(question: str, context: dict, call_fn, history: list | None = None, now: datetime | None = None,
        retries: int = 2, wait=None) -> dict:
    import time
    wait = wait or time.sleep
    now = now or datetime.now(timezone.utc)
    q = clean_question(question)
    if not q:
        return {"ok": False, "question": "", "error": "પ્રશ્ન ખાલી છે"}
    prompt = build_prompt(q, context, history)
    text = call_fn(prompt)
    for attempt in range(retries):
        if not advisor.unavailable(text) or not any(k in text.lower() for k in advisor.TRANSIENT):
            break
        wait(2 * (attempt + 1))
        text = call_fn(prompt)
    ok = not advisor.unavailable(text)
    return {"ok": ok, "question": q, "answer": text if ok else None, "model": advisor.model_name(),
            "prompt_version": PROMPT_VERSION, "context": context, "created_at": now.isoformat(timespec="seconds"),
            "error": None if ok else advisor.friendly_error(text)}


def asked_today(db, now: datetime | None = None) -> int:
    today = (now or datetime.now(IST)).astimezone(IST).date()
    n = 0
    for ev in db.get_audit_events(EVENT, limit=200):
        ts = ev.timestamp if ev.timestamp.tzinfo else ev.timestamp.replace(tzinfo=timezone.utc)
        n += ts.astimezone(IST).date() == today
    return n


def recent(db, limit: int = 10) -> list:
    return [ev.payload or {} for ev in db.get_audit_events(EVENT, limit=limit)]


def save(db, record: dict) -> None:
    from database.models import AuditEvent
    db.save_audit_event(AuditEvent(timestamp=datetime.now(timezone.utc), event_type=EVENT, symbol=None,
                                   payload=json.loads(json.dumps(record, ensure_ascii=False, default=str))))
