"""Market backdrop ("macro") — information only. Nothing here changes a rule, a mode or a trade.

Shown on the 🧭 Mode screen and given to "Garud ને પૂછો" as context:
  India VIX, US dollar-rupee, Brent crude, US 10-year yield, gold (GOLDBEES ETF, rupees),
  and breadth = how many of today's NIFTY 50 stocks close above their 200-day average.
FII/DII flows are not included: there is no reliable free source.
"""
from datetime import date

TICKERS = (  # label, yfinance ticker, unit
    ("India VIX", "^INDIAVIX", ""),
    ("ડૉલર-રૂપિયો (USD/INR)", "USDINR=X", "₹"),
    ("Brent crude", "BZ=F", "$"),
    ("US 10-વર્ષ yield", "^TNX", "%"),
    ("સોનું (GOLDBEES)", "GOLDBEES.NS", "₹"),
)
MONTH = 21   # trading days


def change_row(label: str, series: list, unit: str = "") -> dict:
    """series = [(date, close)] oldest first."""
    pts = [(d, float(c)) for d, c in series if c is not None and c == c]
    if not pts:
        return {"label": label, "ok": False}
    last_d, last = pts[-1]

    def chg(k):
        return round((last / pts[-1 - k][1] - 1) * 100, 2) if len(pts) > k and pts[-1 - k][1] else None
    return {"label": label, "ok": True, "date": str(last_d), "last": round(last, 2), "unit": unit,
            "chg_1d": chg(1), "chg_1m": chg(MONTH)}


def vix_note(v):
    if v is None:
        return ""
    return "શાંત બજાર" if v < 13 else "સામાન્ય" if v <= 20 else "ગભરાટ / મોટી વધઘટ"


def breadth(closes: dict) -> dict:
    """closes = {symbol: [close, ...]} oldest first. Counts stocks with >= 200 closes."""
    above = total = 0
    for px in closes.values():
        px = [float(c) for c in px if c is not None and c == c]
        if len(px) < 200:
            continue
        total += 1
        above += px[-1] > sum(px[-200:]) / 200
    return {"above": above, "total": total, "pct": round(above / total * 100, 1) if total else None}


def breadth_note(pct):
    if pct is None:
        return ""
    return "મોટાભાગના શેર મજબૂત" if pct >= 60 else "મિશ્ર" if pct >= 40 else "મોટાભાગના શેર નબળા"


def summary(rows: list, b: dict) -> dict:
    """Compact facts for display and for the AI context."""
    out = {r["label"]: {k: r.get(k) for k in ("last", "chg_1d", "chg_1m", "date")} for r in rows if r.get("ok")}
    vix = next((r for r in rows if r.get("ok") and r["label"] == "India VIX"), None)
    out["vix_note"] = vix_note(vix["last"]) if vix else ""
    out["breadth_nifty50_above_200dma"] = b
    out["breadth_note"] = breadth_note(b.get("pct"))
    return out


def fetch(today: date | None = None) -> dict:
    """Downloads ~15 months of daily closes (yfinance). Errors are reported, never raised."""
    import yfinance as yf
    from backtest import nifty50_history as nh
    today = today or date.today()
    rows, errors = [], []
    for label, t, unit in TICKERS:
        try:
            df = yf.Ticker(t).history(period="3mo").dropna(subset=["Close"])
            rows.append(change_row(label, [(ts.date(), c) for ts, c in zip(df.index, df["Close"])], unit))
        except Exception as e:
            rows.append({"label": label, "ok": False})
            errors.append(f"{t}: {str(e)[:80]}")
    syms = sorted(nh.members_on(today))
    closes = {}
    try:
        df = yf.download([s + ".NS" for s in syms], period="15mo", interval="1d", progress=False,
                         auto_adjust=True, threads=True)["Close"]
        for s in syms:
            col = s + ".NS"
            if col in df:
                closes[s] = list(df[col].dropna())
    except Exception as e:
        errors.append(f"breadth: {str(e)[:80]}")
    b = breadth(closes)
    return {"rows": rows, "breadth": b, "summary": summary(rows, b), "errors": errors}
