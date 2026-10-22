"""Market backdrop (macro) — pure calculations, no download."""
from datetime import date, timedelta

from backtest import macro

D = [date(2026, 1, 1) + timedelta(days=i) for i in range(40)]


def test_change_row_day_and_month():
    r = macro.change_row("India VIX", [(d, 10 + i) for i, d in enumerate(D)])
    assert r["ok"] and r["last"] == 49 and r["date"] == str(D[-1])
    assert r["chg_1d"] == round((49 / 48 - 1) * 100, 2)
    assert r["chg_1m"] == round((49 / 28 - 1) * 100, 2)
    assert macro.change_row("x", [])["ok"] is False
    assert macro.change_row("x", [(D[0], 5.0)])["chg_1d"] is None


def test_vix_and_breadth_notes():
    assert macro.vix_note(11) == "શાંત બજાર" and macro.vix_note(16) == "સામાન્ય" and "ગભરાટ" in macro.vix_note(25)
    assert macro.vix_note(None) == ""
    assert "મજબૂત" in macro.breadth_note(70) and macro.breadth_note(50) == "મિશ્ર" and "નબળા" in macro.breadth_note(20)


def test_breadth_counts_only_full_history():
    up = [100 + i for i in range(250)]           # last close above its 200-day average
    down = [400 - i for i in range(250)]         # below
    short = [1, 2, 3]                            # ignored
    b = macro.breadth({"A": up, "B": down, "C": short, "D": up})
    assert b == {"above": 2, "total": 3, "pct": 66.7}
    assert macro.breadth({})["pct"] is None


def test_summary_for_ai():
    rows = [macro.change_row("India VIX", [(d, 12.0) for d in D]), {"label": "Brent crude", "ok": False}]
    s = macro.summary(rows, {"above": 20, "total": 50, "pct": 40.0})
    assert s["India VIX"]["last"] == 12.0 and "Brent crude" not in s
    assert s["vix_note"] == "શાંત બજાર" and s["breadth_note"] == "મિશ્ર"
