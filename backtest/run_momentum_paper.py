"""Automatic run of the monthly momentum PAPER portfolios (backtest/momentum_paper.py).
Called by .github/workflows/rule_paper_trading.yml after the other paper tests. Never places orders.
Works only on completed daily closes, so it is safe at any run time; the evening run does the work.
Telegram: on a rebalance or an error (once per day), a Friday-evening summary, and every manual run."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import momentum200 as m2  # noqa: E402
from backtest import momentum_paper as mp  # noqa: E402
from backtest.backtest_engine import charges_for  # noqa: E402
from backtest import nifty50_history as nh  # noqa: E402
from backtest import sectors  # noqa: E402
from backtest.backtest_engine import _nifty_series  # noqa: E402

CANDIDATES = tuple(dict.fromkeys(m2.NIFTY200_TODAY + nh.all_symbols()))
STALE_DAYS = 6            # calendar days without a new NIFTY close before rebalancing is refused
SECTOR_WARN_PCT = 40      # information only: one industry above this share of the holdings
DRAWDOWN_ALERT_PCT = 15   # Telegram warning when a paper portfolio is this far below its peak


def _money(v: float) -> str:
    return f"Rs.{v:,.0f}"


def decide(data, pid: str, i_sig: int, held: set, weak_switch: bool = True) -> tuple:
    if pid == "M2":
        return m2.select(data, i_sig, CANDIDATES, held, weak_switch=weak_switch)
    w = m2.g_weights(data.mkt, i_sig, nh.members_on, weak_switch=weak_switch)
    return w, set(w)


def closes_for(symbols, day, loader=None) -> dict:
    from data.yfinance_loader import YFinanceLoader
    loader = loader or YFinanceLoader()
    out = {}
    start = datetime.combine(day, datetime.min.time()) - timedelta(days=12)
    end = datetime.combine(day, datetime.min.time()) + timedelta(days=1)
    for s in symbols:
        try:
            bars = [b for b in loader.get_historical_bars(s, start, end) if b.timestamp.date() <= day]
            if bars:
                out[s] = float(bars[-1].close)
        except Exception:
            pass
    return out


def run(db, now, kill: bool = False, nifty=None, load_fn=None, closes_fn=None, weak_switch: bool = True) -> dict:
    """weak_switch=False exists ONLY for the dry-run rehearsal of the buying path."""
    """Returns {'lines': [...], 'activity': bool, 'errors': [...]}. Injectable data for tests."""
    lines, errors, activity = [], [], False
    nifty = nifty if nifty is not None else _nifty_series(now.replace(tzinfo=None) - timedelta(days=60),
                                                          now.replace(tzinfo=None) + timedelta(days=1))
    dates = [d for d, _ in nifty]
    last = mp.completed_dates(dates, now)
    if last < 1:
        return {"lines": ["NIFTY data unavailable"], "activity": False, "errors": ["no NIFTY data"]}
    nifty_close = dict(nifty)
    states = {pid: mp.latest_state(db, pid) for pid in mp.PORTFOLIOS}
    due = {pid: mp.due_month_ends(dates, last, st.get("month")) for pid, st in states.items()}
    if (now.date() - dates[last]).days > STALE_DAYS:
        # fail closed: never rebalance on old prices (a long holiday is < 7 days)
        errors.append(f"NIFTY data looks stale (last close {dates[last]}) — no rebalance until fresh data")
        due = {pid: [] for pid in due}
    data = None
    if any(due.values()):
        try:
            data, _start, _errs = (load_fn or (lambda: m2.load(CANDIDATES, dates[last], nh.ALIASES, eval_days=30)))()
        except Exception as e:
            errors.append(f"momentum data download failed: {str(e)[:150]}")
    for pid, st in states.items():
        if data is None:
            break
        mdates = data.mkt.dates
        for m in due[pid]:
            try:
                sig_day, fill_day = dates[m], dates[m + 1]
                if sig_day not in mdates or fill_day not in mdates:
                    errors.append(f"{pid}: price history missing for {sig_day}/{fill_day}")
                    break
                i_sig, i_fill = mdates.index(sig_day), mdates.index(fill_day)
                want, held = decide(data, pid, i_sig, set(st.get("held") or []), weak_switch)
                syms = set(want) | set(st.get("units") or {})
                prices = {s: data.mkt.price(s, i_fill) for s in syms if data.mkt.price(s, i_fill)}
                new = mp.rebalance(st, prices, want, fill_day, allow_buys=not kill, cm=charges_for(fill_day))
                weak = weak_switch and not data.mkt.regime_bull(i_sig)
                new.update({"month": f"{sig_day:%Y-%m}", "held": sorted(held), "signal_date": str(sig_day),
                            "fill_date": str(fill_day), "weak_market": weak, "kill_switch": kill,
                            "nifty": nifty_close.get(fill_day)})
                mp.save(db, mp.EV_REBAL, new)
                mp.save(db, mp.EV_NAV, {"portfolio": pid, "date": str(fill_day), "value": new["value"],
                                        "nifty": nifty_close.get(fill_day)})
                st = states[pid] = new
                activity = True
                buys = [f"{t['symbol']} x{t['qty']}" for t in new["trades"] if t["side"] == "BUY"]
                sells = [f"{t['symbol']} x{t['qty']}" for t in new["trades"] if t["side"] == "SELL"]
                lines.append(f"📦 {pid} {mp.PORTFOLIOS[pid]} — month-end {sig_day:%d %b}, traded at {fill_day:%d %b} close"
                             + (" · NIFTY weak → liquid fund" if weak else "")
                             + (" · kill switch ON: no buys" if kill else ""))
                lines.append(f"   BUY: {', '.join(buys) or '—'}")
                lines.append(f"   SELL: {', '.join(sells) or '—'}")
                lines.append(f"   value {_money(new['value'])} · cash {_money(new['cash'])} · {len(new['units'])} stocks")
                conc = sectors.concentration({x: q * prices.get(x, 0) for x, q in new["units"].items()})
                if conc:
                    lines.append("   sectors: " + " · ".join(f"{k} {v:.0f}%" for k, v in conc[:3])
                                 + (f" ⚠️ {conc[0][0]} above {SECTOR_WARN_PCT}%" if conc[0][1] > SECTOR_WARN_PCT else ""))
            except Exception as e:
                errors.append(f"{pid} rebalance failed: {type(e).__name__}: {str(e)[:150]}")
                break
    # daily value at the close
    day = dates[last]
    for pid, st in states.items():
        if not st.get("as_of") or mp.nav_saved(db, pid, day):
            continue
        try:
            units = st.get("units") or {}
            prices = (closes_fn or closes_for)(list(units), day) if units else {}
            value = mp.mark(st, prices, day)
            mp.save(db, mp.EV_NAV, {"portfolio": pid, "date": str(day), "value": value,
                                    "nifty": nifty_close.get(day)})
            values = [(ev.payload or {}).get("value") for ev in db.get_audit_events(mp.EV_NAV, limit=3000)
                      if (ev.payload or {}).get("portfolio") == pid]
            peak = max([v for v in values if v] + [mp.capital_of(pid)])
            dd = (peak - value) / peak * 100 if peak > 0 else 0.0
            if dd >= DRAWDOWN_ALERT_PCT:
                errors.append(f"{pid} is {dd:.1f}% below its peak (alert level {DRAWDOWN_ALERT_PCT}%; "
                              f"backtest worst was ~18-19%) — rules continue unchanged")
        except Exception as e:
            errors.append(f"{pid} daily value failed: {str(e)[:150]}")
    return {"lines": lines, "activity": activity, "errors": errors}


def status_lines(db) -> list:
    out = []
    base_nifty = mp.first_nifty(db)
    for pid, name in mp.PORTFOLIOS.items():
        st = mp.latest_state(db, pid)
        navs = [ev.payload for ev in db.get_audit_events(mp.EV_NAV, limit=400) if (ev.payload or {}).get("portfolio") == pid]
        if not st.get("as_of"):
            out.append(f"📦 {pid} {name}: starts with the {mp.START_SIGNAL:%d %b %Y} month-end "
                       f"(paper {_money(mp.capital_of(pid))})")
            continue
        latest = max(navs, key=lambda p: p["date"]) if navs else {"value": st["value"], "date": st["as_of"], "nifty": None}
        ret = (latest["value"] / mp.capital_of(pid) - 1) * 100
        nifty_ret = ((latest["nifty"] / base_nifty - 1) * 100) if (latest.get("nifty") and base_nifty) else None
        out.append(f"📦 {pid}: {_money(latest['value'])} ({ret:+.1f}%) on {latest['date']} · {len(st.get('units') or {})} stocks"
                   + (f" · NIFTY {nifty_ret:+.1f}% same period" if nifty_ret is not None else ""))
    return out


class MemoryDB:
    """In-memory stand-in for the database (dry run: nothing is ever saved)."""

    def __init__(self):
        self.events = []

    def get_audit_events(self, event_type, limit=100):
        return [e for e in reversed(self.events) if e.event_type == event_type][:limit]

    def save_audit_event(self, event):
        self.events.append(event)


def dry_run(now, send, **run_kwargs) -> int:
    """Rehearsal on REAL prices: pretends the paper portfolios started at the previous month-end
    and shows what they would have done — nothing is written to the database. Pass 1 follows the
    real rule; pass 2 ignores the weak-market switch so the buying path is always exercised."""
    original = mp.START_SIGNAL
    mp.START_SIGNAL = now.date().replace(day=1) - timedelta(days=7)   # catches last month's final session
    lines, ok = [f"🧪 DRY RUN (nothing saved) — momentum paper as if started last month-end · {now:%Y-%m-%d %H:%M} IST"], True
    try:
        for label, switch in (("1) real rule", True), ("2) buying-path check (weak-market switch ignored)", False)):
            db = MemoryDB()
            try:
                res = run(db, now, weak_switch=switch, **run_kwargs)
            except Exception as e:
                res = {"lines": [], "activity": False, "errors": [f"crashed: {type(e).__name__}: {e}"]}
            lines.append(f"— {label}")
            lines += res["lines"] or ["(no month-end found to rehearse)"]
            if res["errors"]:
                lines.append("⚠️ " + "; ".join(res["errors"][:5]))
            lines += status_lines(db)
            bought = any(ev.event_type == mp.EV_REBAL and (ev.payload or {}).get("units") for ev in db.events)
            ok = ok and res["activity"] and not res["errors"] and (switch or bought)
    finally:
        mp.START_SIGNAL = original
    lines.append("✅ Dry run OK — the real run will work the same way on 2 Nov." if ok
                 else "❌ Dry run found a problem — send this message to Claude.")
    text = "\n".join(lines)
    print(text)
    send(text)
    return 0 if ok else 1


def main() -> int:
    from backtest.run_rule_paper import _first_time_today, send_telegram
    if os.getenv("MOMENTUM_DRY_RUN", "").strip() == "1":
        return dry_run(datetime.now(mp.IST), send_telegram)
    from config.settings import load_settings
    from database.db import Database
    settings = load_settings()
    if settings.database_url.startswith("sqlite"):
        print("DATABASE_URL is not the hosted database — refusing to run.")
        return 1
    kill = os.getenv("GARUD_KILL_SWITCH", "").strip().upper() in ("ON", "1", "TRUE", "YES")
    manual = os.getenv("RUN_SOURCE", "").strip().lower() == "manual"
    db = Database(settings)
    db.connect()
    now = datetime.now(mp.IST)
    try:
        res = run(db, now, kill=kill)
    except Exception as e:
        res = {"lines": [], "activity": False, "errors": [f"momentum paper run crashed: {type(e).__name__}: {e}"]}
    lines = [f"📦 Garud momentum paper portfolios — {now:%Y-%m-%d %H:%M} IST"] + res["lines"]
    if res["errors"]:
        lines.append("⚠️ " + "; ".join(res["errors"][:5]))
    friday_evening = now.weekday() == 4 and now.time() >= mp.CLOSE_DONE
    if manual or res["activity"] or friday_evening:
        lines += status_lines(db)
    text = "\n".join(lines)
    print(text)
    if manual:
        send_telegram(text)
    elif res["activity"] or res["errors"]:
        if _first_time_today(db, "momentum", now, "\n".join(lines[1:])):
            send_telegram(text)
    elif friday_evening and _first_time_today(db, "momentum_weekly", now):
        send_telegram(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
