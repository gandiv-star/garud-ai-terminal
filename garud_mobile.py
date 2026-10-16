"""Garud mobile app screens (dark + gold). Read-only: never writes trades or places orders.

streamlit_app.py calls nav() at the top; for every view except "tools" it calls render()
and stops, so the older analysis terminal stays available under 🛠 Tools unchanged.
"""
import html
from datetime import date, datetime, timedelta, timezone

import streamlit as st

IST = timezone(timedelta(hours=5, minutes=30))
GOLD, GREEN, RED, MUTED = "#D4AF37", "#2ECC71", "#E5534B", "#9AA0AC"

VIEWS = {"🏠 આજ": "home", "📈 Trades": "trades", "🎯 Options": "options",
         "🔬 સંશોધન": "research", "🛠 Tools": "tools"}

REGIME_GU = {
    "STRONG_BULL": ("મજબૂત તેજી", GREEN), "MODERATE_BULL": ("તેજી", GREEN),
    "WEAK_BULL": ("હળવી તેજી", GREEN), "SIDEWAYS": ("Sideways", GOLD),
    "WEAK_BEAR": ("નબળું / મંદી તરફ", RED), "MODERATE_BEAR": ("મંદી", RED), "STRONG_BEAR": ("ભારે મંદી", RED),
}

BASE_CSS = f"""
<style>
#MainMenu, footer, header[data-testid="stHeader"] {{visibility: hidden; height: 0;}}
.block-container {{padding-top: 0.6rem;}}
.g-top {{display:flex; justify-content:space-between; align-items:center; margin: 4px 2px 10px;}}
.g-brand {{font-size: 1.45rem; font-weight: 800; color: {GOLD}; letter-spacing: .5px;}}
.g-sub {{color: {MUTED}; font-size: .8rem;}}
.g-badge {{border: 1px solid {GOLD}; color: {GOLD}; border-radius: 999px; padding: 2px 10px; font-size: .72rem; font-weight: 700;}}
.g-card {{background: #161A23; border: 1px solid #262B38; border-radius: 16px; padding: 14px 16px; margin-bottom: 12px;}}
.g-card h4 {{margin: 0 0 8px; font-size: .82rem; color: {MUTED}; font-weight: 600; text-transform: uppercase; letter-spacing: .6px;}}
.g-big {{font-size: 1.7rem; font-weight: 800; line-height: 1.1;}}
.g-row {{display:flex; justify-content:space-between; align-items:center; padding: 7px 0; border-bottom: 1px solid #222734;}}
.g-row:last-child {{border-bottom: none;}}
.g-l {{font-weight: 600;}}
.g-s {{color: {MUTED}; font-size: .78rem;}}
.g-bar {{height: 6px; background: #262B38; border-radius: 999px; overflow: hidden; margin-top: 6px;}}
.g-bar > div {{height: 100%; background: linear-gradient(90deg, {GOLD}, #F1D27A);}}
.g-pill {{display:inline-block; border-radius: 999px; padding: 1px 9px; font-size: .72rem; font-weight: 700;}}
.g-grid {{display:grid; grid-template-columns: 1fr 1fr; gap: 10px;}}
div[data-testid="stSegmentedControl"] button, div[role="radiogroup"] label {{font-size: .85rem;}}
</style>
"""
APP_CSS = "<style>.block-container {max-width: 640px; padding-bottom: 3rem;}</style>"


# ------------------------------------------------------------------ helpers
def _e(x) -> str:
    return html.escape(str(x))


def _money(v, sign=True) -> str:
    if v is None:
        return "—"
    s = f"{abs(v):,.0f}"
    return (("+" if v > 0 else "−" if v < 0 else "") if sign else ("−" if v < 0 else "")) + "₹" + s


def _col(v) -> str:
    return GREEN if (v or 0) > 0 else RED if (v or 0) < 0 else MUTED


def card(title: str, body: str) -> None:
    st.markdown(f'<div class="g-card"><h4>{_e(title)}</h4>{body}</div>', unsafe_allow_html=True)


def row(left: str, right: str, sub: str = "", right_color: str | None = None) -> str:
    rc = f' style="color:{right_color};font-weight:700"' if right_color else ' style="font-weight:700"'
    sub_html = f'<div class="g-s">{sub}</div>' if sub else ""
    return f'<div class="g-row"><div><div class="g-l">{left}</div>{sub_html}</div><div{rc}>{right}</div></div>'


def bar(frac: float) -> str:
    return f'<div class="g-bar"><div style="width:{max(0, min(frac, 1)) * 100:.0f}%"></div></div>'


def _to_ist_date(ts):
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(IST).date()


# ------------------------------------------------------------------ data (cached)
def _db(settings):
    from database.db import Database
    db = Database(settings)
    db.connect()
    return db


@st.cache_data(ttl=300, show_spinner=False)
def load_market() -> dict:
    from backtest.backtest_engine import _nifty_series, _regime_at
    now = datetime.now(IST).replace(tzinfo=None)
    s = _nifty_series(now - timedelta(days=420), now + timedelta(days=1))
    closes = [c for _, c in s]
    out = {"date": str(s[-1][0]) if s else None, "close": closes[-1] if closes else None,
           "chg": (closes[-1] / closes[-2] - 1) * 100 if len(closes) > 1 else None}
    out["regime"] = _regime_at(closes).regime.value if len(closes) > 1 else None
    return out


@st.cache_data(ttl=300, show_spinner=False)
def load_trades(_settings, key: str) -> list:
    from backtest import paper_rule
    rows = []
    for t in _db(_settings).get_trades(limit=5000):
        if t.strategy_name not in paper_rule.RULE_IDS:
            continue
        rows.append({"rule": t.strategy_name, "symbol": t.symbol, "entry": t.entry_price, "stop": t.stop_price,
                     "qty": t.quantity, "entry_date": _to_ist_date(t.timestamp),
                     "exit": t.exit_price, "exit_date": _to_ist_date(t.exit_timestamp), "pnl": t.realized_pnl})
    return rows


@st.cache_data(ttl=600, show_spinner=False)
def last_prices(symbols: tuple) -> dict:
    from data.yfinance_loader import YFinanceLoader
    loader, out = YFinanceLoader(), {}
    end = datetime.now(IST).replace(tzinfo=None) + timedelta(days=1)
    for s in symbols:
        try:
            bars = loader.get_historical_bars(s, end - timedelta(days=10), end)
            if bars:
                out[s] = float(bars[-1].close)
        except Exception:
            pass
    return out


@st.cache_data(ttl=300, show_spinner=False)
def load_options(_settings, key: str) -> dict:
    from backtest import options_paper as op
    db = _db(_settings)
    ent = [e.payload for e in db.get_audit_events("OPT_ENTRY", limit=500) if (e.payload or {}).get("rule") == op.RULE_ID]
    ext = [e.payload for e in db.get_audit_events("OPT_EXIT", limit=500) if (e.payload or {}).get("rule") == op.RULE_ID]
    return {"entries": ent, "exits": ext}


@st.cache_data(ttl=900, show_spinner=False)
def load_benchmarks(_settings, key: str) -> dict:
    from backtest import rule_report
    return rule_report.stored_benchmarks(_db(_settings))


def _rules():
    from backtest import paper_rule
    return paper_rule.RULES


def rule_summary(rule, trades: list) -> dict:
    mine = [t for t in trades if t["rule"] == rule.rule_id]
    closed = sorted([t for t in mine if t["exit"] is not None and t["pnl"] is not None], key=lambda t: t["exit_date"])
    wins = [t["pnl"] for t in closed if t["pnl"] > 0]
    losses = [t["pnl"] for t in closed if t["pnl"] <= 0]
    return {"closed": closed, "open": [t for t in mine if t["exit"] is None],
            "net": round(sum(t["pnl"] for t in closed), 2),
            "pf": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None}


def unrealised(open_trades: list, prices: dict) -> float:
    return round(sum((prices[t["symbol"]] - t["entry"]) * t["qty"] for t in open_trades if t["symbol"] in prices), 2)


# ------------------------------------------------------------------ navigation
def nav(settings) -> str:
    """Brand header + screen picker. Returns the chosen view key."""
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    now = datetime.now(IST)
    mode = getattr(getattr(settings, "trading_mode", None), "value", "PAPER")
    st.markdown(
        f'<div class="g-top"><div><div class="g-brand">🦅 GARUD</div>'
        f'<div class="g-sub">{now:%d %b %Y, %H:%M} IST</div></div>'
        f'<span class="g-badge">{_e(mode)}</span></div>', unsafe_allow_html=True)
    labels = list(VIEWS)
    picker = getattr(st, "segmented_control", None)
    if picker:
        choice = picker("view", labels, default=labels[0], label_visibility="collapsed", key="_g_nav")
    else:
        choice = st.radio("view", labels, horizontal=True, label_visibility="collapsed", key="_g_nav")
    view = VIEWS.get(choice or labels[0], "home")
    if view != "tools":
        st.markdown(APP_CSS, unsafe_allow_html=True)
    return view


def render(view: str, settings) -> None:
    key = datetime.now(IST).strftime("%Y%m%d%H%M")[:11]   # cache key changes every 10 minutes
    pages = {"home": home, "trades": trades_page, "options": options_page, "research": research_page}
    try:
        pages[view](settings, key)
    except Exception as e:
        card("ભૂલ", f'<div class="g-s">આ સ્ક્રીન લોડ ન થઈ: {_e(e)}</div>')
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ------------------------------------------------------------------ screens
def market_card() -> None:
    try:
        m = load_market()
        reg, col = REGIME_GU.get(m["regime"], (m["regime"] or "—", MUTED))
        chg = m["chg"]
        body = (f'<div style="display:flex;justify-content:space-between;align-items:flex-end">'
                f'<div><div class="g-s">NIFTY 50 · {_e(m["date"])}</div>'
                f'<div class="g-big">{m["close"]:,.0f}</div></div>'
                f'<div style="color:{_col(chg)};font-weight:800;font-size:1.1rem">{chg:+.2f}%</div></div>'
                f'<div style="margin-top:8px">બજારની સ્થિતિ: <span class="g-pill" '
                f'style="background:{col}22;color:{col}">{_e(reg)}</span></div>')
    except Exception as e:
        body = f'<div class="g-s">બજારનો ડેટા મળ્યો નહીં: {_e(e)}</div>'
    card("બજાર", body)


def home(settings, key) -> None:
    market_card()
    trades = load_trades(settings, key)
    rules = _rules()
    sums = {r.rule_id: rule_summary(r, trades) for r in rules}
    open_all = [t for s in sums.values() for t in s["open"]]
    prices = last_prices(tuple(sorted({t["symbol"] for t in open_all}))) if open_all else {}
    unreal = unrealised(open_all, prices)
    realised = round(sum(s["net"] for s in sums.values()), 2)
    opt = load_options(settings, key)
    opt_net = round(sum(x.get("net_pnl", 0) for x in opt["exits"]), 2)
    opt_open = len({e["id"] for e in opt["entries"]} - {x["id"] for x in opt["exits"]})

    body = (f'<div class="g-grid">'
            f'<div><div class="g-s">ખુલ્લા trades નો નફો/નુકસાન</div>'
            f'<div class="g-big" style="color:{_col(unreal)}">{_money(unreal)}</div>'
            f'<div class="g-s">{len(open_all)} stocks ખુલ્લા</div></div>'
            f'<div><div class="g-s">બંધ trades નું કુલ</div>'
            f'<div class="g-big" style="color:{_col(realised + opt_net)}">{_money(realised + opt_net)}</div>'
            f'<div class="g-s">stocks {_money(realised)} · options {_money(opt_net)}</div></div></div>'
            f'<div class="g-s" style="margin-top:8px">📄 Paper trading — અસલ પૈસા નહીં</div>')
    card("આજનો સારાંશ", body)

    bench = {}
    try:
        bench = load_benchmarks(settings, key[:9])
    except Exception:
        pass
    rows_html = ""
    from backtest import rule_report
    for r in rules:
        s = sums[r.rule_id]
        n = len(s["closed"])
        try:
            status = rule_report.checkpoint_status([t["pnl"] for t in s["closed"]], bench.get(r.rule_id))
        except Exception:
            status = ""
        rows_html += (row(_e(r.title), _money(s["net"]), f'{n}/{r.target_trades} બંધ · {len(s["open"])} ખુલ્લા'
                          + (f' · PF {s["pf"]}' if s["pf"] is not None else "") + f'<br>{_e(status)}',
                          _col(s["net"])) + bar(n / r.target_trades))
    from backtest import options_paper as op
    n_opt = len(opt["exits"])
    rows_html += row("🎯 Options condor v1", _money(opt_net),
                     f"{n_opt}/{op.TARGET_TRADES} બંધ · {opt_open} ખુલ્લા", _col(opt_net)) + bar(n_opt / op.TARGET_TRADES)
    card("Tests ની પ્રગતિ (30 trades પછી નિર્ણય)", rows_html)

    events = []
    for t in trades:
        if t["exit_date"]:
            events.append((t["exit_date"], f'🔴 {t["symbol"]} બંધ', _money(t["pnl"]), _col(t["pnl"])))
        if t["entry_date"]:
            events.append((t["entry_date"], f'🟢 {t["symbol"]} ખરીદ્યો', f'₹{t["entry"]:,.1f}', None))
    for e in opt["entries"]:
        events.append((date.fromisoformat(e["time"][:10]), f'🎯 Condor {e["id"]} ખુલ્યો', _money(e["credit"] * e["lot"]), None))
    for x in opt["exits"]:
        events.append((date.fromisoformat(x["time"][:10]), f'🎯 Condor {x["id"]} {x["reason"]}', _money(x["net_pnl"]), _col(x["net_pnl"])))
    events.sort(key=lambda e: e[0], reverse=True)
    body = "".join(row(_e(t), r, f"{d:%d %b}", c) for d, t, r, c in events[:8]) or '<div class="g-s">હજી કોઈ પ્રવૃત્તિ નથી</div>'
    card("તાજેતરની પ્રવૃત્તિ", body)


def trades_page(settings, key) -> None:
    trades = load_trades(settings, key)
    titles = {r.rule_id: r.title for r in _rules()}
    open_t = [t for t in trades if t["exit"] is None]
    prices = last_prices(tuple(sorted({t["symbol"] for t in open_t}))) if open_t else {}
    body = ""
    for t in sorted(open_t, key=lambda t: t["entry_date"] or date.min, reverse=True):
        p = prices.get(t["symbol"])
        pnl = (p - t["entry"]) * t["qty"] if p else None
        pct = (p / t["entry"] - 1) * 100 if p else None
        body += row(_e(t["symbol"]),
                    (_money(pnl) + (f" ({pct:+.1f}%)" if pct is not None else "")) if p else "—",
                    f'{_e(titles.get(t["rule"], t["rule"]))} · {t["entry_date"]:%d %b} · ખરીદી ₹{t["entry"]:,.1f} · '
                    f'stop ₹{t["stop"]:,.1f} · હાલ {("₹%.1f" % p) if p else "—"}', _col(pnl))
    card(f"ખુલ્લા trades ({len(open_t)})", body or '<div class="g-s">કોઈ trade ખુલ્લો નથી</div>')
    closed = sorted([t for t in trades if t["exit"] is not None], key=lambda t: t["exit_date"] or date.min, reverse=True)
    body = "".join(row(_e(t["symbol"]), _money(t["pnl"]),
                       f'{_e(titles.get(t["rule"], t["rule"]))} · {t["entry_date"]:%d %b} → {t["exit_date"]:%d %b} · '
                       f'₹{t["entry"]:,.1f} → ₹{t["exit"]:,.1f}', _col(t["pnl"])) for t in closed[:30])
    card(f"બંધ trades ({len(closed)})", body or '<div class="g-s">હજી કોઈ trade બંધ થયો નથી</div>')
    guard_card(trades)


def guard_card(trades: list) -> None:
    """What the live safety limits would have done if all paper trades had been real."""
    from backtest import live_guard
    cfg = live_guard.GuardConfig.from_env()
    s = live_guard.simulate(trades, cfg)
    reasons = ", ".join(f"{k}: {v}" for k, v in s["reasons"].items()) or "—"
    body = (row("Trades (બધા tests)", f'{s["taken"]}/{s["trades"]} લેવાત',
                f'{s["reduced"]} નાના કરાત · {s["skipped"]} અટકાવાત · કારણ: {_e(reasons)}')
            + row("બંધ trades નું પરિણામ", _money(s["pnl_with_guard"]),
                  f'મર્યાદા વગર {_money(s["pnl_without"])}', _col(s["pnl_with_guard"]))
            + row("અત્યારે રોકાયેલી મૂડી", f'₹{s["open_value_now"]:,.0f}',
                  f'મર્યાદા ₹{cfg.capital:,.0f} · વધુમાં વધુ {cfg.max_open} trades · એક stock ≤ {cfg.max_stock_pct:.0f}% · '
                  f'મહિને નુકસાન ≤ ₹{cfg.monthly_loss_limit:,.0f}'
                  + (f' · દિવસે ≤ ₹{cfg.daily_loss_limit:,.0f}' if cfg.daily_loss_limit > 0 else '')))
    card("🛡 અસલ trading ની સુરક્ષા — જો આ trades અસલ હોત", body)


def options_page(settings, key) -> None:
    from backtest import options_paper as op
    opt = load_options(settings, key)
    closed_ids = {x["id"] for x in opt["exits"]}
    open_c = [e for e in opt["entries"] if e["id"] not in closed_ids]
    for e in open_c:
        legs = e["legs"]
        body = row("Expiry", _e(e["expiry"]), f'lot {e["lot"]} · ખુલ્યો {e["time"][:10]}')
        for leg in legs:
            body += row(f'{"વેચ્યો" if leg["side"] < 0 else "ખરીદ્યો"} {leg["strike"]:.0f} {leg["type"]}',
                        f'₹{leg.get("entry", 0):,.2f}', "", RED if leg["side"] < 0 else GREEN)
        body += row("મળેલું premium", _money(e["credit"] * e["lot"]),
                    f'નફો લેવાશે: બાકી ≤ {e["credit"] * op.TAKE_PROFIT:.1f} · stop: ≥ {e["credit"] * op.STOP_MULT:.1f} (દરેક unit)', GOLD)
        card(f"ચાલુ condor {e['id']}", body)
    if not open_c:
        card("ચાલુ condor", '<div class="g-s">અત્યારે કોઈ condor ખુલ્લો નથી. બુધ–શુક્ર સવારે, આવતા અઠવાડિયાની '
                            'expiry માટે આપમેળે ખુલશે.</div>')
    nets = [x["net_pnl"] for x in opt["exits"]]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    pf = round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None
    body = (row("બંધ condors", f"{len(nets)}/{op.TARGET_TRADES}") + bar(len(nets) / op.TARGET_TRADES)
            + row("કુલ નફો/નુકસાન", _money(sum(nets)), "", _col(sum(nets)))
            + row("Profit factor", pf if pf is not None else "—", "પાસ થવા ≥ 1.2 અને FD 7% થી વધુ વાર્ષિક"))
    for x in sorted(opt["exits"], key=lambda x: x["time"], reverse=True)[:20]:
        body += row(_e(x["id"]), _money(x["net_pnl"]), f'{_e(x["reason"])} · {x["time"][:10]}', _col(x["net_pnl"]))
    card("Options test — NIFTY iron condor", body)


RESEARCH = [
    ("Regime પ્રમાણે strategy બદલવી", "❌", "20,000 trades: નવા ડેટામાં પસંદગી PF 0.75 vs બધું 0.73 — ફાયદો નથી"),
    ("Swing strategies (10/40 દિવસ)", "⏳", "Backtest માં કોઈ સ્પષ્ટ પાસ નહીં; v1, v2, v3 paper માં ચકાસાય છે"),
    ("Momentum (સાચું NIFTY 50 લિસ્ટ, 15 વર્ષ)", "❌", "12.3% vs NIFTY 11.7% — 2011-21 માં index થી પાછળ"),
    ("NIFTY index ખરીદો અને રાખો (15 વર્ષ)", "✅", "11.7% વાર્ષિક vs FD 7% — પણ વચ્ચે ખરાબ વર્ષો"),
    ("Intraday (ORB, Gap) — 2 વર્ષ", "❌", "ખર્ચ પહેલાં ₹24–44 નફો, ખર્ચ ₹180 — નુકસાન"),
    ("NIFTY options વેચવા (iron condor)", "⏳", "21 ઓક્ટો 2026 થી paper માં, 30 trades પછી નિર્ણય"),
]


def research_page(settings, key) -> None:
    body = "".join(row(f"{icon} {_e(t)}", "", _e(d)) for t, icon, d in RESEARCH)
    card("શું ચકાસ્યું અને શું મળ્યું", body)
    card("Garud નો નિયમ", '<div>પહેલાં સાબિતી, પછી પૈસા. દરેક નિયમ ચલાવતાં <b>પહેલાં</b> નક્કી થાય છે; '
                         'પરિણામ જોઈને નિયમ બદલાતો નથી. 30 trades પછી જ પાસ/નાપાસ.</div>')
