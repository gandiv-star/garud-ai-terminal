""""Garud ને પૂછો" — prompt rules, retries, daily cap, storage. No network."""
from datetime import datetime, timedelta, timezone

from llm import ask_garud as ag

IST = timezone(timedelta(hours=5, minutes=30))


class Ev:
    def __init__(self, ts, payload=None):
        self.timestamp, self.payload = ts, payload or {}


class DB:
    def __init__(self, events=()):
        self.events, self.saved = list(events), []

    def get_audit_events(self, kind, limit=100):
        return self.events[:limit] if kind == ag.EVENT else []

    def save_audit_event(self, ev):
        self.saved.append(ev)


def test_context_drops_empty_and_keeps_standing_facts():
    ctx = ag.build_context(mode={"mode": "DEFENSIVE"}, rules=[], studies=None)
    assert ctx["today_mode"] == {"mode": "DEFENSIVE"} and "swing_paper_rules" not in ctx
    assert "PAPER" in ctx["standing_facts"]["money"]


def test_context_is_size_limited():
    ctx = ag.build_context(rules=[{"x": "y" * 50000}])
    assert ctx["note"] == "context shortened" and len(ctx["json"]) == ag.MAX_CONTEXT_CHARS


def test_prompt_has_rules_facts_question_and_history():
    p = ag.build_prompt("v2 કેમ નુકસાનમાં છે?", {"today_mode": {"mode": "NO TRADE"}}, [("q1", "a1")])
    assert "Use ONLY the JSON facts" in p and "Do NOT recommend buying" in p and "NO TRADE" in p
    assert p.rstrip().endswith("QUESTION: v2 કેમ નુકસાનમાં છે?") and "Q: q1" in p
    assert "માત્ર માહિતી — નિર્ણય Garud ના નિયમો અને તમે જ લો છો." in p


def test_ask_ok_retry_and_unavailable():
    calls = []

    def flaky(prompt):
        calls.append(prompt)
        return "(AI reasoning unavailable: 503 overloaded)" if len(calls) == 1 else "જવાબ"
    r = ag.ask("  આજે   બજાર? ", {}, flaky, wait=lambda s: None)
    assert r["ok"] and r["answer"] == "જવાબ" and r["question"] == "આજે બજાર?" and len(calls) == 2
    assert r["prompt_version"] == ag.PROMPT_VERSION
    bad = ag.ask("x", {}, lambda p: "(AI reasoning unavailable: no GEMINI_API_KEY configured.)", wait=lambda s: None)
    assert not bad["ok"] and bad["answer"] is None and bad["error"]
    assert ag.ask("   ", {}, lambda p: "x")["ok"] is False


def test_question_length_limit():
    assert len(ag.clean_question("અ" * 2000)) == ag.MAX_QUESTION_CHARS


def test_daily_count_and_save():
    now = datetime(2026, 10, 22, 10, 0, tzinfo=IST)
    db = DB([Ev(datetime(2026, 10, 22, 2, 0, tzinfo=timezone.utc)),          # 07:30 IST today
             Ev(datetime(2026, 10, 21, 20, 0)),                               # naive UTC = 22 Oct 01:30 IST
             Ev(datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc))])         # yesterday
    assert ag.asked_today(db, now) == 2
    ag.save(db, {"question": "q", "answer": "a", "context": {"d": now}})
    assert db.saved[0].event_type == ag.EVENT and db.saved[0].payload["answer"] == "a"
