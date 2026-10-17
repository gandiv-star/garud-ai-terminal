"""Today's Trading Mode — a transparent, rule-based answer to "what is Garud ready to do today?"

Version mode_v1 (registered 17 Oct 2026). It does NOT pick strategies by forecast and makes
no profit claim: the evidence matrix (8 Oct 2026) found no out-of-sample benefit from choosing
strategies by regime. The mode is simply WHICH pre-registered paper rules may open new trades
under today's NIFTY regime, with every reason shown:

  1. NIFTY regime from the last COMPLETED daily close (same _regime_at as every backtest).
  2. A stock rule is ACTIVE only if (a) its allowed_regimes include the regime AND (b) its
     strategy's own regime filter accepts the regime; otherwise it is REJECTED with the reason.
  3. Kill switch ON -> NO TRADE (exits still run).
  4. Mode label = strategy families of the active rules, else DEFENSIVE (no new stock trades).
  5. Context only (never changes the decision): 20-day volatility vs its 1-year range,
     20-day NIFTY return, distance to SMA50/SMA200, and the exact conditions for the next regime.
The options condor test is listed separately (it does not depend on the regime).
"""
import math
from datetime import date, datetime

from backtest.backtest_engine import _regime_at

VERSION = "mode_v1"
REGISTERED = "2026-10-17"
ALL_REGIMES = ("STRONG_BULL", "MODERATE_BULL", "WEAK_BULL", "SIDEWAYS", "WEAK_BEAR",
               "MODERATE_BEAR", "STRONG_BEAR", "CRISIS")
FAMILY = {"Volatility Expansion": "VOLATILITY EXPANSION", "Trend Following": "TREND FOLLOWING",
          "Mean Reversion": "MEAN REVERSION", "Breakout": "BREAKOUT", "Momentum": "MOMENTUM"}


def strategy_regimes(strategy_name: str) -> set:
    """Regimes a strategy's own code accepts (read from the strategy modules where they declare it)."""
    if strategy_name == "Trend Following":
        from strategies.trend_following import FAVORABLE_REGIMES
        return {r.value for r in FAVORABLE_REGIMES}
    if strategy_name == "Volatility Expansion":
        return set(ALL_REGIMES) - {"CRISIS"}
    return set(ALL_REGIMES)


def _sma(xs, n):
    return sum(xs[-n:]) / n if len(xs) >= n else None


def _vol20(closes):
    if len(closes) < 21:
        return None
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(len(closes) - 20, len(closes))]
    m = sum(rets) / len(rets)
    return math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1)) * math.sqrt(252) * 100


def context(closes: list) -> dict:
    price = closes[-1] if closes else None
    s50, s200 = _sma(closes, 50), _sma(closes, 200)
    vol = _vol20(closes)
    hist = [v for v in (_vol20(closes[:i]) for i in range(max(21, len(closes) - 252), len(closes) + 1)) if v]
    # mid-rank percentile: ties count half, so a flat history reads 50 (not 100)
    pct = (round((sum(1 for v in hist if v < vol) + 0.5 * sum(1 for v in hist if v == vol)) / len(hist) * 100)
           if vol is not None and hist else None)
    return {
        "price": price, "sma50": s50, "sma200": s200,
        "vs_sma50_pct": (price / s50 - 1) * 100 if s50 else None,
        "vs_sma200_pct": (price / s200 - 1) * 100 if s200 else None,
        "ret20_pct": (price / closes[-21] - 1) * 100 if len(closes) > 20 else None,
        "vol20_pct": vol, "vol_percentile": pct,
        "risk_level": None if pct is None else "HIGH" if pct >= 80 else "LOW" if pct <= 20 else "NORMAL",
    }


def bull_conditions(ctx: dict) -> list:
    """The three conditions of MODERATE_BULL (the regime where trend rules switch on)."""
    p, s50, s200 = ctx["price"], ctx["sma50"], ctx["sma200"]
    if None in (p, s50, s200):
        return []
    return [("NIFTY > SMA50", p > s50, f"{p:,.0f} vs {s50:,.0f}"),
            ("NIFTY > SMA200", p > s200, f"{p:,.0f} vs {s200:,.0f}"),
            ("SMA50 > SMA200", s50 > s200, f"{s50:,.0f} vs {s200:,.0f}")]


def decide(closes: list, last_date: date | None, rules, kill_switch: bool = False,
           now: datetime | None = None) -> dict:
    if len(closes) < 200:
        return {"version": VERSION, "mode": "NO TRADE", "regime": None, "active": [], "rejected": [],
                "reason": "NIFTY history too short to judge the regime (need 200 sessions)",
                "data_date": str(last_date) if last_date else None, "decided_at": (now or datetime.now()).isoformat()}
    regime = _regime_at(closes).regime.value
    ctx = context(closes)
    active, rejected = [], []
    for r in rules:
        if regime not in r.allowed_regimes:
            rejected.append((r.title, f"rule allows only {', '.join(r.allowed_regimes)}"))
        elif regime not in strategy_regimes(r.strategy_name):
            rejected.append((r.title, f"{r.strategy_name} strategy does not buy in {regime}"))
        else:
            active.append((r.title, r.strategy_name))
    if kill_switch:
        mode, reason = "NO TRADE", "Kill switch ON — no new entries (exits continue)"
    elif not active:
        mode, reason = "DEFENSIVE", f"No pre-registered stock rule may enter in {regime}"
    else:
        fams = sorted({FAMILY.get(s, s.upper()) for _, s in active})
        mode = " + ".join(fams)
        reason = f"NIFTY regime {regime}: " + ", ".join(t for t, _ in active) + " may open new paper trades"
    return {"version": VERSION, "mode": mode, "regime": regime, "reason": reason,
            "active": active, "rejected": rejected, "context": ctx, "next_regime": bull_conditions(ctx),
            "data_date": str(last_date) if last_date else None,
            "decided_at": (now or datetime.now()).isoformat(timespec="minutes")}
