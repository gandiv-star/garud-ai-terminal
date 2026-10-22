"""Garud mobile app screens (dark + gold). Read-only: never writes trades or places orders.

streamlit_app.py calls nav() at the top; for every view except "tools" it calls render()
and stops, so the older analysis terminal stays available under 🛠 Tools unchanged.
"""
import html
import os
from datetime import date, datetime, timedelta, timezone

import streamlit as st

IST = timezone(timedelta(hours=5, minutes=30))
GOLD, GREEN, RED, MUTED = "#C9A227", "#22C55E", "#EF4444", "#94A3B8"
AMBER, BLUE = "#F59E0B", "#4C8DFF"
CARD, BORDER, LINE = "#12233D", "#1E3A5F", "#1A2F4D"

VIEWS = {"🏠 આજ": "home", "🧭 Mode": "mode", "🔎 Scanner": "scanner", "📊 Chart": "chart",
         "📈 Trades": "trades", "🛡 Risk": "risk", "🎯 Options": "options",
         "🔬 સંશોધન": "research", "🤖 પૂછો": "ask", "🩺 Health": "health", "🛠 Tools": "tools"}
DOT = {"ok": GREEN, "warn": AMBER, "bad": RED, "na": MUTED}

REGIME_GU = {
    "STRONG_BULL": ("મજબૂત તેજી", GREEN), "MODERATE_BULL": ("તેજી", GREEN),
    "WEAK_BULL": ("હળવી તેજી", GREEN), "SIDEWAYS": ("Sideways", AMBER),
    "WEAK_BEAR": ("નબળું / મંદી તરફ", RED), "MODERATE_BEAR": ("મંદી", RED), "STRONG_BEAR": ("ભારે મંદી", RED),
}

BASE_CSS = f"""
<style>
#MainMenu, footer, header[data-testid="stHeader"] {{visibility: hidden; height: 0;}}
.block-container {{padding-top: 0.6rem;}}
.g-top {{display:flex; justify-content:space-between; align-items:center; margin: 4px 2px 10px;}}
.g-brand {{font-size: 1.45rem; font-weight: 800; color: {GOLD}; letter-spacing: .5px;}}
.g-sub {{color: {MUTED}; font-size: .8rem;}}
.g-badge {{border: 1px solid {BLUE}; color: {BLUE}; border-radius: 999px; padding: 2px 10px; font-size: .72rem; font-weight: 700;}}
.g-card {{background: {CARD}; border: 1px solid {BORDER}; border-radius: 16px; padding: 14px 16px; margin-bottom: 12px;}}
.g-card h4 {{margin: 0 0 8px; font-size: .82rem; color: {MUTED}; font-weight: 600; text-transform: uppercase; letter-spacing: .6px;}}
.g-big {{font-size: 1.7rem; font-weight: 800; line-height: 1.1;}}
.g-row {{display:flex; justify-content:space-between; align-items:center; padding: 7px 0; border-bottom: 1px solid {LINE};}}
.g-row:last-child {{border-bottom: none;}}
.g-l {{font-weight: 600;}}
.g-s {{color: {MUTED}; font-size: .78rem;}}
.g-bar {{height: 6px; background: {LINE}; border-radius: 999px; overflow: hidden; margin-top: 6px;}}
.g-bar > div {{height: 100%; background: {BLUE};}}
.g-chips {{display:flex; flex-wrap:wrap; gap:6px; margin: 0 2px 10px;}}
.g-chip {{border:1px solid {BORDER}; background:{CARD}; border-radius:999px; padding:2px 9px; font-size:.72rem; white-space:nowrap;}}
.g-dot {{display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:5px; vertical-align:middle;}}
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
def load_mode(_settings, key: str) -> dict:
    """Today's mode computed live from completed NIFTY closes (same engine as the pipeline)."""
    from backtest import paper_rule, trading_mode
    now = paper_rule.now_ist()
    nifty = paper_rule.MarketData(now).nifty_completed()
    kill = False
    try:
        runs = _db(_settings).get_audit_events("PIPELINE_RUN", limit=1)
        kill = bool(runs and (runs[0].payload or {}).get("kill_switch"))
    except Exception:
        pass
    return trading_mode.decide([c for _, c in nifty], nifty[-1][0] if nifty else None, paper_rule.RULES, kill, now)


@st.cache_data(ttl=600, show_spinner=False)
def load_mode_history(_settings, key: str) -> list:
    return [(e.timestamp, e.payload or {}) for e in _db(_settings).get_audit_events("TRADING_MODE", limit=15)]


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


def unrealised_net(open_trades: list, prices: dict) -> float:
    """Open P&L after the buy charges already paid and the sell charges an exit would cost,
    on the same basis as closed-trade P&L (paper_rule.net_pnl)."""
    from backtest.backtest_engine import ChargeModel
    cm = ChargeModel()
    return round(sum((prices[t["symbol"]] - t["entry"]) * t["qty"] - cm.buy_charges(t["entry"] * t["qty"])
                     - cm.sell_charges(prices[t["symbol"]] * t["qty"]) for t in open_trades if t["symbol"] in prices), 2)


@st.cache_data(ttl=120, show_spinner=False)
def load_health(_settings, key: str) -> dict:
    import garud_health as gh
    now = datetime.now(IST)
    res = gh.run_db_checks(lambda: _db(_settings), now)
    try:
        market, err = load_market(), ""
    except Exception as e:
        market, err = None, str(e)[:160]
    mode = getattr(getattr(_settings, "trading_mode", None), "value", "")
    checks = gh.all_checks(res, market, err, now, dict(os.environ), mode)
    live = ((res["last_run"].payload or {}).get("live") if res.get("last_run") else None) or None
    return {"checks": checks, "errors": gh.recent_errors(res["runs"]), "overall": gh.overall(checks),
            "checked": now.strftime("%H:%M"), "live": live}


def pipeline_guard(h: dict):
    """(GuardConfig, source note, problems) as the AUTOMATIC run last reported it — the app's own
    environment does not hold the GitHub LIVE_* variables, so it must not read them itself."""
    from backtest import live_guard
    live = (h or {}).get("live") or {}
    if live.get("guard"):
        return live_guard.GuardConfig.from_dict(live["guard"]), "છેલ્લા automatic run મુજબ", live.get("problems") or []
    return live_guard.GuardConfig(), "default (automatic run એ હજી limits report કર્યા નથી)", []


def _chip(label: str, status: str) -> str:
    return f'<span class="g-chip"><span class="g-dot" style="background:{DOT.get(status, MUTED)}"></span>{_e(label)}</span>'


def status_bar(settings) -> None:
    """Always-visible status: mode, data, runs, broker, AI, risk — from real checks."""
    try:
        h = load_health(settings, datetime.now(IST).strftime("%Y%m%d%H%M")[:11])
        by = {c.name: c for c in h["checks"]}
        pick = [("Market data (NIFTY)", "Data"), ("Automatic runs", "Runs"), ("Broker sandbox (Upstox)", "Broker"),
                ("AI (Gemini)", "AI"), ("Risk / kill switch", "Risk")]
        chips = "".join(_chip(f"{short}: {by[n].value}", by[n].status) for n, short in pick if n in by)
        st.markdown(f'<div class="g-chips">{chips}</div>', unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f'<div class="g-chips">{_chip("Status unavailable: " + str(e)[:60], "bad")}</div>',
                    unsafe_allow_html=True)


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
    status_bar(settings)
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
    pages = {"home": home, "mode": mode_page, "scanner": scanner_page, "chart": chart_page,
             "trades": trades_page, "risk": risk_page, "options": options_page, "research": research_page,
             "ask": ask_page, "health": health_page}
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


def mode_color(mode: str) -> str:
    return RED if mode == "NO TRADE" else AMBER if mode == "DEFENSIVE" else BLUE


def home(settings, key) -> None:
    try:
        m = load_mode(settings, key)
        card("🧭 આજનો Trading Mode",
             f'<div class="g-big" style="color:{mode_color(m["mode"])};font-size:1.25rem">{_e(m["mode"])}</div>'
             f'<div class="g-s">{_e(m["reason"])}</div>'
             f'<div class="g-s" style="margin-top:4px">વિગત માટે 🧭 Mode tab · {_e(m["version"])}</div>')
    except Exception as e:
        card("🧭 આજનો Trading Mode", f'<div class="g-s">Unavailable: {_e(e)}</div>')
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
            f'<div class="g-s">{len(open_all)} stocks ખુલ્લા · charges પછી ≈ {_money(unrealised_net(open_all, prices))}'
            f' · છેલ્લા બંધ ભાવે{"" if len(prices) == len({t["symbol"] for t in open_all}) else " (અમુક ભાવ મળ્યા નહીં)"}</div></div>'
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
        events.append((date.fromisoformat(e["time"][:10]), f'🎯 Condor {e["id"]} ખુલ્યો',
                       "premium " + _money(e["credit"] * e["lot"], sign=False), MUTED))   # not a profit yet
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
    guard_card(trades, load_health(settings, key))
    execution_card(settings, key)


@st.cache_data(ttl=300, show_spinner=False)
def load_execution(_settings, key: str) -> dict:
    import garud_risk as gk
    from backtest import paper_rule, sandbox_mirror
    db = _db(_settings)
    trades = [t for t in db.get_trades(limit=5000) if t.strategy_name in paper_rule.RULE_IDS]
    expected = {o["internal_order_id"] for o in sandbox_mirror.expected_orders(trades, frozenset())}
    ok = [e.payload or {} for e in db.get_audit_events(sandbox_mirror.EVENT_OK, limit=5000)]
    bad = [e.payload or {} for e in db.get_audit_events(sandbox_mirror.EVENT_FAIL, limit=2000)]
    live = {k: len(db.get_audit_events(k, limit=2000)) for k in ("LIVE_ENTRY", "LIVE_GTT", "LIVE_EXIT", "LIVE_ERROR")}
    return {"sandbox": gk.sandbox_status(expected, ok, bad), "live": live}


def execution_card(settings, key) -> None:
    from backtest.backtest_engine import ChargeModel
    try:
        ex = load_execution(settings, key)
    except Exception as e:
        card("Execution", f'<div class="g-s">Unavailable: {_e(e)}</div>')
        return
    sb, lv = ex["sandbox"], ex["live"]
    cm = ChargeModel()
    sb_status = GREEN if not sb["missing"] else AMBER
    body = (row("📄 Paper", "ચાલુ", "Garud ના પોતાના નિયમોથી નોંધાયેલા trades — ઉપરના બધા આંકડા આ જ છે")
            + row("🧪 Sandbox (Upstox test orders)", f'{sb["placed"]}/{sb["expected"]}',
                  ("બધા paper orders sandbox માં પહોંચ્યા" if not sb["missing"] else
                   f'{len(sb["missing"])} બાકી/નિષ્ફળ: ' + ", ".join(_e(x) for x in sb["missing"][:4])), sb_status)
            + row("💰 Live (અસલ પૈસા)", "OFF" if not lv["LIVE_ENTRY"] else f'{lv["LIVE_ENTRY"]} entries',
                  f'live orders: entries {lv["LIVE_ENTRY"]} · stops {lv["LIVE_GTT"]} · exits {lv["LIVE_EXIT"]} · errors {lv["LIVE_ERROR"]}',
                  GREEN if not lv["LIVE_ERROR"] else RED)
            + row("ખર્ચની ધારણા (delivery)", "", f'STT {cm.stt_pct}% બંને બાજુ · exchange {cm.exchange_charges_pct}% · '
                  f'stamp {cm.stamp_duty_pct}% (ખરીદી) · SEBI {cm.sebi_charges_pct}% · GST 18% · brokerage ₹{cm.brokerage_flat:.0f}'))
    card("Execution — paper / sandbox / live અલગ", body + '<div class="g-s" style="margin-top:6px">ત્રણેયના P&L ક્યારેય ભેગા થતા નથી.</div>')


def risk_page(settings, key) -> None:
    import garud_risk as gk
    from backtest import live_guard, paper_rule
    trades = load_trades(settings, key)
    open_t = [t for t in trades if t["exit"] is None]
    prices = last_prices(tuple(sorted({t["symbol"] for t in open_t}))) if open_t else {}
    ex = gk.paper_exposure(open_t, prices)
    h = load_health(settings, key)
    by = {c.name: c for c in h["checks"]}
    elig = "".join(row(f'<span class="g-dot" style="background:{DOT.get(by[n].status, MUTED)}"></span>{_e(n)}',
                       _e(by[n].value), _e(by[n].detail)) for n in ("Live orders", "Risk / kill switch") if n in by)
    try:
        m = load_mode(settings, key)
        elig += row("આજનો mode", _e(m["mode"]), _e(m["reason"]), mode_color(m["mode"]))
    except Exception:
        pass
    card("Trading eligibility", elig)
    titles = {r.rule_id: r.title for r in paper_rule.RULES}
    body = row("ખુલ્લા trades", str(ex["count"]), f'{ex["priced"]} ના હાલના ભાવ મળ્યા')
    body += row("રોકાયેલી રકમ (entry ભાવે)", f'₹{ex["total"]:,.0f}', f'દરેક rule ની મૂડી ₹{gk.CAPITAL_PER_RULE:,.0f}')
    for rid, v in ex["by_rule"].items():
        body += row(_e(titles.get(rid, rid)), f'₹{v:,.0f}', f'{v / gk.CAPITAL_PER_RULE * 100:.0f}% of ₹1 લાખ',
                    RED if v > gk.CAPITAL_PER_RULE else None) + bar(v / gk.CAPITAL_PER_RULE)
    body += row("બધા stops વાગે તો નુકસાન", _money(-ex["open_risk"]), "હાલના ભાવથી stop સુધી (gap-down માં વધી શકે)", RED)
    body += row("ખુલ્લા trades નો નફો/નુકસાન", _money(ex["unrealised"]), "", _col(ex["unrealised"]))
    card("📄 Paper exposure", body)
    tot = ex["total"] or 1
    sec = "".join(row(_e(k), f'{v / tot * 100:.0f}%', f'₹{v:,.0f}', AMBER if v / tot > 0.30 else None)
                  for k, v in ex["by_sector"].items())
    if ex["multi_rule_symbols"]:
        sec += row("એક stock ઘણા rules માં", ", ".join(_e(s) for s in ex["multi_rule_symbols"]),
                   "paper માં બરાબર; live માં guard એક stock ને 20% સુધી રાખશે", AMBER)
    card("Concentration (sector) — 30% ઉપર પીળું", sec or '<div class="g-s">કોઈ ખુલ્લો trade નથી</div>')
    st_rows = "".join(row(f'{_e(s)} · {_e(titles.get(r, r))}', f'{d:+.1f}%', f'હાલ ₹{p:,.1f} · stop ₹{stp:,.1f}',
                          AMBER if d <= gk.STOP_NEAR_PCT else None) for s, r, p, stp, d in ex["stops"][:10])
    card(f"Stop-loss થી અંતર ({len(ex['near_stop'])} trade {gk.STOP_NEAR_PCT:.0f}% અંદર)",
         st_rows or '<div class="g-s">ભાવ ઉપલબ્ધ નથી</div>')
    dd = ""
    for r in paper_rule.RULES:
        closed = sorted([t for t in trades if t["rule"] == r.rule_id and t["pnl"] is not None], key=lambda t: t["exit_date"])
        mdd, cur = gk.drawdown([t["pnl"] for t in closed])
        dd += row(_e(r.title), _money(-mdd) if mdd else "₹0", f'હાલનો ઘટાડો {_money(-cur) if cur else "₹0"} · {len(closed)} બંધ trades',
                  RED if mdd else None)
    card("Drawdown (બંધ trades, paper)", dd)
    cfg, src, problems = pipeline_guard(h)
    today = datetime.now(IST).date()
    month_paper = gk.month_realised([t for t in trades if t["pnl"] is not None], today)
    lim = (row("Live: મૂડી / trades / એક stock", f'₹{cfg.capital:,.0f}', f'વધુમાં વધુ {cfg.max_open} trades · એક stock ≤ {cfg.max_stock_pct:.0f}% · {src}')
           + row("Live: મહિનાની નુકસાન મર્યાદા", f'₹{cfg.monthly_loss_limit:,.0f}', "પહોંચે તો નવી ખરીદી આપમેળે બંધ")
           + row("Live: દિવસની મર્યાદા", "OFF" if cfg.daily_loss_limit <= 0 else f'₹{cfg.daily_loss_limit:,.0f}',
                 "16 ઓક્ટો એ તમારા નિર્ણયથી બંધ" if cfg.daily_loss_limit <= 0 else "નવી ખરીદી આપમેળે બંધ")
           + (row("⚠️ Live limit setting ખોટું", "BUY બંધ", _e("; ".join(problems)), RED) if problems else "")
           + row("આ મહિને paper નું બંધ P&L", _money(month_paper), "માત્ર માહિતી — મર્યાદા live પર લાગે", _col(month_paper)))
    try:
        from backtest import options_paper as op
        on = sum(x.get("net_pnl", 0) for x in load_options(settings, key)["exits"])
        lim += row("Options circuit breaker", "PAUSED" if on <= op.MAX_DRAWDOWN_STOP else "OK",
                   f'કુલ {_money(on)} · ₹{-op.MAX_DRAWDOWN_STOP:,.0f} નુકસાને નવા condors બંધ',
                   RED if on <= op.MAX_DRAWDOWN_STOP else GREEN)
    except Exception:
        pass
    card("Limits અને circuit breakers", lim + '<div class="g-s" style="margin-top:6px">Risk નિયમો ક્યારેય AI થી બદલાતા નથી.</div>')


def guard_card(trades: list, h: dict | None = None) -> None:
    """What the live safety limits would have done if all paper trades had been real."""
    from backtest import live_guard
    cfg, src, problems = pipeline_guard(h)
    s = live_guard.simulate(trades, cfg)
    reasons = ", ".join(f"{k}: {v}" for k, v in s["reasons"].items()) or "—"
    body = (row("Trades (બધા tests)", f'{s["taken"]}/{s["trades"]} લેવાત',
                f'{s["reduced"]} નાના કરાત · {s["skipped"]} અટકાવાત · કારણ: {_e(reasons)}')
            + row("બંધ trades નું પરિણામ", _money(s["pnl_with_guard"]),
                  f'મર્યાદા વગર {_money(s["pnl_without"])}', _col(s["pnl_with_guard"]))
            + row("અત્યારે રોકાયેલી મૂડી", f'₹{s["open_value_now"]:,.0f}',
                  f'મર્યાદા ₹{cfg.capital:,.0f} · વધુમાં વધુ {cfg.max_open} trades · એક stock ≤ {cfg.max_stock_pct:.0f}% · '
                  f'મહિને નુકસાન ≤ ₹{cfg.monthly_loss_limit:,.0f}'
                  + (f' · દિવસે ≤ ₹{cfg.daily_loss_limit:,.0f}' if cfg.daily_loss_limit > 0 else '') + f' · {src}'))
    if problems:
        body += row("⚠️ Live limit setting ખોટું", "BUY બંધ", _e("; ".join(problems)), RED)
    card("🛡 અસલ trading ની સુરક્ષા — જો આ trades અસલ હોત", body)


def options_page(settings, key) -> None:
    from backtest import options_paper as op
    opt = load_options(settings, key)
    closed_ids = {x["id"] for x in opt["exits"]}
    open_c = [e for e in opt["entries"] if e["id"] not in closed_ids]
    for e in open_c:
        legs = e["legs"]
        body = row("Expiry", _e(e["expiry"]), f'lot {e["lot"]} · ખુલ્યો {e["time"][:10]}'
                   + (f' · સૌથી પહોળો bid-ask {e["max_spread_pct"]}%' if e.get("max_spread_pct") is not None else ""))
        for leg in legs:
            body += row(f'{"વેચ્યો" if leg["side"] < 0 else "ખરીદ્યો"} {leg["strike"]:.0f} {leg["type"]}',
                        f'₹{leg.get("entry", 0):,.2f}', "", RED if leg["side"] < 0 else GREEN)
        body += row("મળેલું premium", _money(e["credit"] * e["lot"]),
                    f'નફો લેવાશે: બાકી ≤ {e["credit"] * op.TAKE_PROFIT:.1f} · stop: ≥ {e["credit"] * op.STOP_MULT:.1f} (દરેક unit)', BLUE)
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


def mode_page(settings, key) -> None:
    m = load_mode(settings, key)
    ctx = m.get("context") or {}
    reg, rcol = REGIME_GU.get(m.get("regime"), (m.get("regime") or "—", MUTED))
    card("આજનો Trading Mode",
         f'<div class="g-big" style="color:{mode_color(m["mode"])}">{_e(m["mode"])}</div>'
         f'<div style="margin:6px 0">{_e(m["reason"])}</div>'
         f'<div class="g-s">Regime: <span class="g-pill" style="background:{rcol}22;color:{rcol}">{_e(reg)}</span> · '
         f'ડેટા {_e(m.get("data_date"))} સુધીનો · નિર્ણય {_e(m.get("decided_at", "")[:16].replace("T", " "))} · '
         f'{_e(m["version"])}</div>')
    body = "".join(row(f"✅ {_e(t)}", "સક્રિય", _e(s_)) for t, s_ in m.get("active", []))
    body += "".join(row(f"⛔ {_e(t)}", "બંધ", _e(why), MUTED) for t, why in m.get("rejected", []))
    body += row("🎯 Options condor v1", "સ્વતંત્ર", "regime પર આધાર નથી · બુધ–શુક્ર સવારે entry window")
    card("કયા rules આજે નવા trades લઈ શકે", body)
    def pct(v):
        return "—" if v is None else f"{v:+.1f}%"
    ev = (row("NIFTY છેલ્લો બંધ", f'{ctx["price"]:,.0f}' if ctx.get("price") else "—")
          + row("SMA50 થી અંતર", pct(ctx.get("vs_sma50_pct")))
          + row("SMA200 થી અંતર", pct(ctx.get("vs_sma200_pct")))
          + row("20 દિવસનું વળતર", pct(ctx.get("ret20_pct")))
          + row("20 દિવસની volatility", f'{ctx["vol20_pct"]:.1f}%' if ctx.get("vol20_pct") else "—",
                f'છેલ્લા 1 વર્ષમાં {ctx.get("vol_percentile")}મા percentile પર' if ctx.get("vol_percentile") is not None else "")
          + row("Risk level (માત્ર માહિતી)", _e(ctx.get("risk_level") or "—"), "",
                RED if ctx.get("risk_level") == "HIGH" else GREEN if ctx.get("risk_level") == "LOW" else None))
    card("પુરાવા / indicators", ev)
    conds = "".join(row(f'{"✅" if ok else "❌"} {_e(n)}', _e(v)) for n, ok, v in m.get("next_regime", []))
    card("Mode ક્યારે બદલાશે", (conds + '<div class="g-s" style="margin-top:6px">ત્રણેય ✅ થાય તો regime '
                               'MODERATE_BULL બને: ત્યારે Trend Following (v3) ચાલુ થાય અને v1/v2 નવા trades બંધ કરે.</div>')
         if conds else '<div class="g-s">માહિતી નથી</div>')
    macro_card()
    card("પ્રામાણિક નોંધ", '<div class="g-s">આ mode કોઈ આગાહી નથી. 8 ઓક્ટો 2026 ના evidence matrix માં '
                          '"regime પ્રમાણે strategy બદલવાથી ફાયદો" સાબિત થયો નથી. Mode માત્ર બતાવે છે કે પહેલેથી '
                          'નક્કી કરેલા કયા paper rules આજે trade લેવા લાયક છે. પાસ/નાપાસ 30 trades પછી જ.</div>')
    try:
        hist = load_mode_history(settings, key[:10])
        body = "".join(row(_e(p.get("mode")), _e(p.get("regime")), f'{_e(p.get("day"))} · {_e(p.get("version"))}')
                       for _, p in hist)
        card("Mode નો ઇતિહાસ (રોજ automatic run નોંધે છે)", body or '<div class="g-s">હજી નોંધ નથી — આગલા run થી શરૂ થશે</div>')
    except Exception as e:
        card("Mode નો ઇતિહાસ", f'<div class="g-s">Unavailable: {_e(e)}</div>')


@st.cache_data(ttl=3600, show_spinner=False)
def load_macro(key: str) -> dict:
    from backtest import macro
    return macro.fetch(datetime.now(IST).date())


def macro_card() -> None:
    from backtest import macro
    try:
        mc = load_macro(datetime.now(IST).strftime("%Y%m%d%H"))
    except Exception as e:
        card("બજારનું વાતાવરણ (macro)", f'<div class="g-s">Unavailable: {_e(e)}</div>')
        return
    body = ""
    for r in mc["rows"]:
        if not r.get("ok"):
            body += row(_e(r["label"]), "—", "ડેટા મળ્યો નહીં", MUTED)
            continue
        unit = r.get("unit") or ""
        val = f'{r["last"]:,.2f}%' if unit == "%" else f'{unit}{r["last"]:,.2f}'
        sub = " · ".join(x for x in (
            f'1 દિવસ {r["chg_1d"]:+.2f}%' if r.get("chg_1d") is not None else "",
            f'1 મહિનો {r["chg_1m"]:+.2f}%' if r.get("chg_1m") is not None else "",
            macro.vix_note(r["last"]) if r["label"] == "India VIX" else "", r.get("date") or "") if x)
        body += row(_e(r["label"]), val, _e(sub))
    b = mc["breadth"]
    body += row("NIFTY 50 ના શેર 200-દિવસ સરેરાશથી ઉપર",
                f'{b["above"]}/{b["total"]}' if b.get("total") else "—",
                f'{b["pct"]}% · {macro.breadth_note(b["pct"])}' if b.get("pct") is not None else "ડેટા મળ્યો નહીં",
                GREEN if (b.get("pct") or 0) >= 60 else RED if b.get("pct") is not None and b["pct"] < 40 else AMBER)
    body += ('<div class="g-s" style="margin-top:6px">માત્ર માહિતી — કોઈ નિયમ કે mode આના પરથી બદલાતો નથી. '
             'FII/DII નો વિશ્વસનીય મફત ડેટા નથી, એટલે બતાવ્યો નથી. કલાકે એક વાર તાજું.</div>')
    card("બજારનું વાતાવરણ (macro)", body)


ACTION_COL = {"BUY CANDIDATE": GREEN, "OPEN": BLUE, "WATCH": AMBER, "NO TRADE": MUTED, "DATA ISSUE": RED}
ACTION_GU = {"BUY CANDIDATE": "BUY CANDIDATE — આવતી સવારે paper entry", "OPEN": "હાલ ખુલ્લો",
             "WATCH": "WATCH — signal છે પણ regime રોકે છે", "NO TRADE": "NO TRADE", "DATA ISSUE": "DATA ISSUE"}


@st.cache_data(ttl=600, show_spinner=False)
def load_scan(_settings, key: str):
    ev = _db(_settings).get_audit_events("SCAN_SNAPSHOT", limit=1)
    return (ev[0].payload or {}) if ev else None


@st.cache_data(ttl=1800, show_spinner=False)
def live_scan(_settings, key: str) -> dict:
    from backtest import paper_rule, scanner
    from strategies.registry import STRATEGY_REGISTRY
    trades = [t for t in _db(_settings).get_trades(limit=5000) if t.strategy_name in paper_rule.RULE_IDS]
    snap = scanner.build_snapshot(paper_rule.MarketData(paper_rule.now_ist()), STRATEGY_REGISTRY, trades)
    snap["built_at"] = datetime.now(IST).isoformat(timespec="minutes") + " (live)"
    return snap


def _px(v) -> str:
    return "—" if v is None else f"₹{v:,.1f}"


def _pc(v, sign=True) -> str:
    return "—" if v is None else (f"{v:+.1f}%" if sign else f"{v:.1f}%")


def scanner_page(settings, key) -> None:
    snap = st.session_state.get("_g_live_scan") or load_scan(settings, key)
    if st.button("🔄 હમણાં નવો scan (આશરે 1 મિનિટ)", use_container_width=True):
        with st.spinner("NIFTY 50 ના બધા stocks ચકાસું છું..."):
            snap = live_scan(settings, key[:10])
            st.session_state["_g_live_scan"] = snap
    if not snap:
        card("Scanner", '<div class="g-s">હજી snapshot નથી — સાંજના automatic run પછી આવશે, અથવા ઉપરનું બટન દબાવો.</div>')
        return
    c = snap.get("counts", {})
    card("Smart Scanner — NIFTY 50 (daily, rule-based)",
         row("ડેટા", _e(snap.get("data_date")), f'regime {_e(snap.get("regime"))} · બન્યો {_e(snap.get("built_at", "")).replace("T", " ")} · {_e(snap.get("version"))}')
         + "".join(row(f'<span class="g-dot" style="background:{ACTION_COL[k]}"></span>{_e(k)}', str(c.get(k, 0)))
                   for k in ACTION_COL)
         + '<div class="g-s" style="margin-top:6px">કોઈ બનાવટી score નથી: rules હા/ના છે, દરેક stock નું કારણ નીચે છે. '
           'Labels કોઈ order નથી — paper entry pipeline જ કરે છે.</div>')
    choice = st.radio("filter", ["બધા", "BUY CANDIDATE", "OPEN", "WATCH", "NO TRADE", "DATA ISSUE"],
                      horizontal=True, label_visibility="collapsed", key="_g_scan_f")
    rows = [r for r in snap.get("rows", []) if choice == "બધા" or r["action"] == choice]
    for r in rows[:60]:
        col = ACTION_COL.get(r["action"], MUTED)
        st.markdown(
            f'<div class="g-card" style="padding:10px 14px;margin-bottom:6px">'
            f'<div style="display:flex;justify-content:space-between"><b>{_e(r["symbol"])}</b>'
            f'<span class="g-pill" style="background:{col}22;color:{col}">{_e(r["action"])}</span></div>'
            f'<div class="g-s">{_px(r["close"])} · {_e(r["date"])} · SMA20 થી {_pc(r["trend_pct"])} · '
            f'10 દિવસ {_pc(r["mom10_pct"])} · ATR {_pc(r["atr_pct"], sign=False)}</div>'
            f'<div style="font-size:.85rem;margin-top:3px">{_e(r["reason"])}</div></div>', unsafe_allow_html=True)
        with st.expander(f'{r["symbol"]} — વિગત'):
            for ch in r.get("checks", []):
                st.markdown(f'- **{ch["rule"]}**: {ch["result"]}' + (f' — {ch.get("why")}' if ch.get("why") else ""))
            if r.get("ref"):
                f = r["ref"]
                st.markdown(f'Reference ({f["rule"]}, છેલ્લા બંધ ₹{f["close"]} પર): stop ₹{f["stop"]} · qty {f["qty"]} · '
                            f'જોખમ ₹{f["risk"]}. અસલ entry આવતી સવારના open પર થશે.')
            st.caption(ACTION_GU.get(r["action"], ""))
            if r["action"] in ("BUY CANDIDATE", "WATCH", "OPEN"):
                ai_block(settings, key, r, snap)


@st.cache_data(ttl=300, show_spinner=False)
def load_ai_advice(_settings, key: str) -> dict:
    out = {}
    for ev in _db(_settings).get_audit_events("AI_ADVICE", limit=300):
        p = ev.payload or {}
        out.setdefault((p.get("symbol"), p.get("data_date")), p)
    return out


def _ai_facts(settings, key, r: dict) -> dict:
    import garud_risk as gk
    from backtest import paper_rule
    from llm import advisor
    try:
        mode = load_mode(settings, key)
    except Exception:
        mode = None
    titles = {x.title: x.rule_id for x in paper_rule.RULES}
    rule_title = (r.get("ref") or {}).get("rule") or next((c["rule"] for c in r.get("checks", [])
                                                           if c.get("result") in ("signal", "open", "blocked by regime")), None)
    rid = titles.get(rule_title)
    try:
        b = load_benchmarks(settings, key[:9]).get(rid) if rid else None
    except Exception:
        b = None
    bench = {"trades": b.get("trades"), "pf": b.get("pf"), "avg_net_rs": b.get("mean"), "win_pct": b.get("win_rate"),
             "period": b.get("period")} if b else None
    trades = load_trades(settings, key)
    closed = [t["pnl"] for t in trades if t["rule"] == rid and t["pnl"] is not None]
    wins, losses = [x for x in closed if x > 0], [x for x in closed if x <= 0]
    paper = {"rule": rule_title, "closed_trades": len(closed), "needed_for_verdict": 30, "net_rs": round(sum(closed), 2),
             "pf": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None}
    sec = gk.SECTOR.get(r["symbol"], "Other")
    sec_open = sum(1 for t in trades if t["exit"] is None and gk.SECTOR.get(t["symbol"], "Other") == sec)
    return advisor.build_facts(r, mode, bench, paper, sec, sec_open)


def _ist_text(iso) -> str:
    """Stored UTC ISO time -> 'YYYY-MM-DD HH:MM' in IST."""
    try:
        t = datetime.fromisoformat(str(iso))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t.astimezone(IST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(iso or "")[:16]


def ai_block(settings, key, r: dict, snap: dict) -> None:
    """Gemini explanation for one scanner row — advisory only, logged, never decides."""
    from llm import advisor
    k = (r["symbol"], r.get("date"))
    try:
        rec = load_ai_advice(settings, key).get(k)
    except Exception:
        rec = None
    if rec is None and st.button("🤖 AI સમજૂતી (Gemini)", key=f"_g_ai_{r['symbol']}"):
        with st.spinner("AI સમજૂતી તૈયાર થાય છે..."):
            from llm.ai_reasoning import AIReasoningEngine
            rec = advisor.advise(_ai_facts(settings, key, r), AIReasoningEngine()._call_gemini)
            if rec["ok"]:
                try:
                    advisor.save(_db(settings), rec)
                    load_ai_advice.clear()
                except Exception as e:
                    st.caption(f"AI જવાબ સાચવી ન શકાયો: {e}")
    if rec is None:
        return
    if not rec.get("ok", True):
        st.warning("AI unavailable — " + str(rec.get("error") or "Gemini જવાબ ન મળ્યો") + ". નિયમ આધારિત માહિતી ઉપર છે.")
        return
    st.markdown(f'<div class="g-s">🤖 AI advisory · {_e(rec.get("model"))} · {_e(rec.get("prompt_version"))} · '
                f'{_e(_ist_text(rec.get("created_at")))} IST · ડેટા {_e(rec.get("data_date"))}</div>',
                unsafe_allow_html=True)
    st.markdown(rec.get("output", ""))


@st.cache_data(ttl=1800, show_spinner=False)
def load_bars(symbol: str, key: str) -> list:
    from data.yfinance_loader import YFinanceLoader
    end = datetime.now(IST).replace(tzinfo=None) + timedelta(days=1)
    return YFinanceLoader().get_historical_bars(symbol, end - timedelta(days=700), end)


def chart_page(settings, key) -> None:
    import garud_chart as gc
    from backtest import paper_rule
    trades = load_trades(settings, key)
    open_syms = sorted({t["symbol"] for t in trades if t["exit"] is None})
    snap = load_scan(settings, key) or {}
    cands = [r["symbol"] for r in snap.get("rows", []) if r["action"] == "BUY CANDIDATE"]
    universe = sorted(set(paper_rule.UNIVERSE_NIFTY50) | set(paper_rule.UNIVERSE_8))
    first = (cands + open_syms + universe)[0]
    sym = st.selectbox("Stock", universe, index=universe.index(first), key="_g_chart_sym")
    span = st.radio("Range", ["3M", "6M", "1Y"], index=1, horizontal=True, key="_g_chart_rng")
    try:
        bars = load_bars(sym, key[:10])
    except Exception as e:
        card("Chart", f'<div class="g-s">ડેટા મળ્યો નહીં: {_e(e)}</div>')
        return
    if len(bars) < 30:
        card("Chart", '<div class="g-s">પૂરતો ડેટા નથી</div>')
        return
    s = gc.series(bars)
    days = {"3M": 92, "6M": 183, "1Y": 366}[span]
    start = gc.start_index(s["dates"], (datetime.now(IST) - timedelta(days=days)).date())
    mine = [t for t in trades if t["symbol"] == sym]
    markers = [(t["entry_date"], t["entry"], "entry", f'Paper BUY ₹{t["entry"]}') for t in mine if t["entry_date"]]
    markers += [(t["exit_date"], t["exit"], "exit", f'Paper exit ₹{t["exit"]} ({_money(t["pnl"])})')
                for t in mine if t["exit_date"] and t["exit"] is not None]
    levels = []
    for t in mine:
        if t["exit"] is None:
            levels += [(t["entry"], f'Entry ₹{t["entry"]:,.1f}', BLUE), (t["stop"], f'Stop ₹{t["stop"]:,.1f}', RED)]
    last = bars[-1]
    try:
        fig = gc.build_figure(s, start, markers, levels, f"{sym} · daily · છેલ્લો ₹{last.close:,.1f}")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
    except Exception as e:
        st.warning(f"Advanced chart unavailable ({e}) — simple chart:")
        st.line_chart({"close": s["close"][start:]})
    r_ = s["rsi"][-1]
    card("આ chart માં શું છે",
         row("છેલ્લો bar", f"{last.timestamp:%d %b %Y}", "માત્ર daily bars — intraday ડેટા નથી")
         + row("RSI14", f"{r_:.0f}" if r_ is not None else "—", "70 ઉપર ઊંચું, 30 નીચે નીચું (માત્ર માહિતી)")
         + row("▲ / ▼ markers", str(len(markers)), "Garud ના અસલ paper trades (ઇતિહાસ) — કોઈ આગાહી નહીં")
         + row("ડૅશ લાઇન", str(len(levels) // 2), "હાલ ખુલ્લા trade ની entry અને stop"))


def health_page(settings, key) -> None:
    import garud_health as gh
    h = load_health(settings, key)
    label = {"ok": "બધું બરાબર", "warn": "ધ્યાન આપવા જેવું", "bad": "તકલીફ છે"}[h["overall"]]
    card("System health", f'<div class="g-big" style="color:{DOT[h["overall"]]}">{label}</div>'
                          f'<div class="g-s">ચકાસ્યું {h["checked"]} IST · app version {gh.APP_VERSION}</div>')
    body = "".join(row(f'<span class="g-dot" style="background:{DOT.get(c.status, MUTED)}"></span>{_e(c.name)}',
                       _e(c.value), _e(c.detail)) for c in h["checks"])
    card("ચકાસણીઓ", body)
    errs = "".join(row(_e(e), "", f"{ts:%d %b %H:%M}") for ts, e in h["errors"])
    card("તાજેતરની data issues (automatic runs)", errs or '<div class="g-s">કોઈ નથી</div>')
    if st.button("🤖 AI ચકાસો (Gemini ને એક નાનો પ્રશ્ન)", use_container_width=True):
        from llm.ai_reasoning import AIReasoningEngine
        ans = AIReasoningEngine()._call_gemini("Reply with exactly: OK")
        ok = ans.strip().upper().startswith("OK")
        card("AI test", f'<div style="color:{GREEN if ok else RED};font-weight:700">'
                        f'{"✅ AI જવાબ આપે છે" if ok else "❌ AI unavailable"}</div><div class="g-s">{_e(ans[:200])}</div>')


@st.cache_data(ttl=600, show_spinner=False)
def load_momentum(_settings, key: str) -> dict:
    from backtest import momentum_paper as mp
    db = _db(_settings)
    return {"rebals": [ev.payload or {} for ev in db.get_audit_events(mp.EV_REBAL, limit=200)],
            "navs": [ev.payload or {} for ev in db.get_audit_events(mp.EV_NAV, limit=3000)]}


@st.cache_data(ttl=900, show_spinner=False)
def load_studies(_settings, key: str) -> dict:
    import garud_research as gr
    return gr.latest_studies(_db(_settings))


def research_page(settings, key) -> None:
    import garud_research as gr
    from backtest import paper_rule, rule_report, trading_mode
    from strategies.registry import STRATEGY_REGISTRY
    card("Research Lab", f'<div class="g-s">{_e(gr.SAME_ASSUMPTIONS)} Backtest ના આંકડા ભૂતકાળના છે — '
                         'અસલ ભવિષ્યનું પરિણામ નથી. નિર્ણય ફક્ત paper (forward) test પરથી.</div>')
    # --- rules: backtest benchmark vs paper
    trades = load_trades(settings, key)
    try:
        benches = load_benchmarks(settings, key[:9])
    except Exception:
        benches = {}
    for r in gr.rule_rows(paper_rule.RULES, trades, benches, rule_report.checkpoint_status):
        b, pp = r["bench"], r["paper"]
        body = row("Backtest (5 વર્ષ)", f'PF {b["pf"]}' if b else "NOT RUN",
                   f'{b["trades"]} trades · avg ₹{b["avg"]} · win {b["win"]}% · {_e(b["period"])}' if b else "benchmark DB માં નથી")
        body += row("Paper (forward, out-of-sample)", f'{pp["closed"]}/{pp["target"]}',
                    f'net {_money(pp["net"])} · avg {_money(pp["avg"]) if pp["avg"] is not None else "—"} · '
                    f'win {pp["win"] if pp["win"] is not None else "—"}% · PF {pp["pf"] if pp["pf"] is not None else "—"}',
                    _col(pp["net"])) + bar(pp["closed"] / pp["target"])
        body += row("Walk-forward / robustness", "NOT TESTED", "આ rule માટે ચલાવ્યું નથી (સાધન 🛠 Tools → Backtest માં છે)", MUTED)
        body += row("Status", "", _e(r["status"]))
        card(f'{r["title"]} · {r["strategy"]}', body + f'<div class="g-s" style="margin-top:6px">{_e(r["describe"])}</div>')
    # --- completed studies
    try:
        studies = load_studies(settings, key[:9])
    except Exception as e:
        studies = {}
        card("Studies", f'<div class="g-s">Unavailable: {_e(e)}</div>')
    for kind, when, sm in gr.study_cards(studies):
        if sm is None:
            card(kind, '<div class="g-s">NOT RUN — DB માં પરિણામ નથી</div>')
            continue
        col = GREEN if sm["pass"] else RED
        body = (f'<div style="color:{col};font-weight:800">{"✅" if sm["pass"] else "❌"} {_e(sm["verdict"])}</div>'
                f'<div class="g-s">ચલાવ્યું {when:%d %b %Y}' + (f' · {_e(sm.get("period"))}' if sm.get("period") else "") + '</div>')
        body += "".join(row(_e(k), "", _e(v)) for k, v in sm["lines"])
        card(sm["title"], body)
    # --- monthly momentum paper portfolios
    try:
        from backtest import momentum_paper as mp
        mom = load_momentum(settings, key)
        for r in gr.momentum_paper_rows(mom["rebals"], mom["navs"], mp.PORTFOLIOS, mp.CAPITALS):
            if not r["started"]:
                card(f'📦 {r["id"]} · {r["name"]} (paper)',
                     row("શરૂઆત", f'{mp.START_SIGNAL:%d %b %Y}', "મહિનાના છેલ્લા દિવસે પસંદગી, બીજા દિવસના બંધ ભાવે ખરીદી · "
                         f'₹{mp.capital_of(r["id"]):,.0f} paper'))
                continue
            body = (row("કિંમત", _money(r["value"], sign=False), f'{r["date"]} · શરૂઆત ₹{r["capital"]:,.0f}', _col(r["ret"]))
                    + row("વળતર", f'{r["ret"]:+.2f}%',
                          f'NIFTY એ જ સમયમાં {r["nifty_ret"]:+.2f}%' if r["nifty_ret"] is not None else "", _col(r["ret"]))
                    + row("સૌથી મોટો ઘટાડો", f'{r["max_dd"]:.1f}%', f'{r["rebalances"]} rebalance · છેલ્લું {r["last_fill"]}')
                    + row("હાલ ટોચથી નીચે", f'{r.get("dd_now") or 0:.1f}%',
                          (f'{r["days_below_peak"]} દિવસથી ટોચ નીચે' if r.get("days_below_peak") else "ટોચ પર"))
                    + row("હાલ", "Liquid fund" if r["weak"] and not r["holdings"] else f'{len(r["holdings"])} શેર',
                          f'રોકડ ₹{(r["cash"] or 0):,.0f}' + (" · બજાર નબળું" if r["weak"] else "")))
            if r["holdings"]:
                body += f'<div class="g-s" style="margin-top:6px">{_e(", ".join(f"{s} x{q}" for s, q in r["holdings"]))}</div>'
            card(f'📦 {r["id"]} · {r["name"]} (paper)', body)
    except Exception as e:
        card("Momentum paper", f'<div class="g-s">Unavailable: {_e(e)}</div>')
    # --- options forward test
    try:
        from backtest import options_paper as op
        opt = load_options(settings, key)
        n = len(opt["exits"])
        card("NIFTY options iron condor (forward paper)",
             row("બંધ condors", f"{n}/{op.TARGET_TRADES}", "Backtest: NOT TESTED (જૂનો options ડેટા મફત નથી)")
             + bar(n / op.TARGET_TRADES)
             + row("કુલ", _money(sum(x.get("net_pnl", 0) for x in opt["exits"])), "", _col(sum(x.get("net_pnl", 0) for x in opt["exits"]))))
    except Exception as e:
        card("Options", f'<div class="g-s">Unavailable: {_e(e)}</div>')
    # --- registry
    body = "".join(row(_e(x["name"]), _e(x["status"]),
                       ("Rules: " + ", ".join(x["rules"]) if x["rules"] else "કોઈ paper rule નથી")
                       + f' · regimes: {_e(x["regimes"])}', BLUE if x["rules"] else MUTED)
                   for x in gr.registry_rows(STRATEGY_REGISTRY, paper_rule.RULES, trading_mode.strategy_regimes))
    card("Strategy registry (8)", body)
    card("Garud નો નિયમ", '<div>પહેલાં સાબિતી, પછી પૈસા. દરેક નિયમ ચલાવતાં <b>પહેલાં</b> નક્કી થાય છે; '
                         'પરિણામ જોઈને નિયમ બદલાતો નથી. 30 trades પછી જ પાસ/નાપાસ.</div>')



# ------------------------------------------------------------------ ask Garud
def ask_context(settings, key) -> dict:
    """Facts for "Garud ને પૂછો" — only numbers Garud already shows on its screens."""
    from llm import ask_garud
    import garud_research as gr
    part = {}

    def grab(name, fn):
        try:
            part[name] = fn()
        except Exception as e:
            part[name] = {"unavailable": str(e)[:120]}

    def mode():
        m = load_mode(settings, key)
        return {k: m.get(k) for k in ("mode", "regime", "reason", "data_date", "context")}

    def rules():
        trades = load_trades(settings, key)
        out = []
        opens = [t for t in trades if t["exit"] is None]
        prices = last_prices(tuple(sorted({t["symbol"] for t in opens}))) if opens else {}
        for r in _rules():
            sm = rule_summary(r, trades)
            out.append({"rule": r.title, "closed": len(sm["closed"]), "target": r.target_trades, "net_closed": sm["net"],
                        "pf": sm["pf"], "unrealised_open": unrealised(sm["open"], prices),
                        "open_positions": [{"symbol": t["symbol"], "entry": t["entry"], "stop": t["stop"], "qty": t["qty"],
                                            "entry_date": t["entry_date"], "last_price": prices.get(t["symbol"])}
                                           for t in sm["open"]],
                        "last_closed": [{"symbol": t["symbol"], "pnl": t["pnl"], "exit_date": t["exit_date"]}
                                        for t in sm["closed"][-5:]]})
        return out

    def options():
        from backtest import options_paper as op
        opt = load_options(settings, key)
        closed = {x["id"] for x in opt["exits"]}
        firsts = [date.fromisoformat(e["time"][:10]) for e in opt["entries"]]
        st_ = op.stats(opt["exits"], min(firsts) if firsts else None, datetime.now(IST).date())
        if st_["closed"] < op.ANNUAL_MIN_CLOSED:
            st_.pop("annual_pct", None)
        return {"stats": st_, "target": op.TARGET_TRADES,
                "open": [{"id": e["id"], "expiry": e["expiry"], "premium_received": round(e["credit"] * e["lot"])}
                         for e in opt["entries"] if e["id"] not in closed],
                "closed": [{"id": x["id"], "reason": x["reason"], "net_pnl": x["net_pnl"]} for x in opt["exits"][-5:]]}

    def momentum():
        from backtest import momentum_paper as mp
        mom = load_momentum(settings, key)
        return [{k: v for k, v in r.items()} for r in gr.momentum_paper_rows(mom["rebals"], mom["navs"], mp.PORTFOLIOS, mp.CAPITALS)]

    def studies():
        return [{"study": sm["title"], "verdict": sm["verdict"], "passed": sm["pass"], "period": sm.get("period"),
                 "lines": sm["lines"]} for _, _, sm in gr.study_cards(load_studies(settings, key[:9])) if sm]

    def macro():
        return load_macro(datetime.now(IST).strftime("%Y%m%d%H"))["summary"]

    def health():
        h = load_health(settings, key)
        return {"overall": h["overall"], "checks": [{"name": c.name, "status": c.status, "value": c.value}
                                                    for c in h["checks"]]}

    for name, fn in (("mode", mode), ("rules", rules), ("options", options), ("momentum", momentum),
                     ("studies", studies), ("macro", macro), ("health", health)):
        grab(name, fn)
    return ask_garud.build_context(**part)


def ask_page(settings, key) -> None:
    from llm import ask_garud
    from llm.ai_reasoning import AIReasoningEngine
    card("🤖 Garud ને પૂછો", '<div class="g-s">Garud ના પોતાના આંકડા (paper trades, momentum, options, mode, બજારનું '
                           'વાતાવરણ, અભ્યાસો) પરથી ગુજરાતીમાં જવાબ. AI ને order મૂકવાની કે નિયમ બદલવાની કોઈ સત્તા નથી; '
                           'દરેક જવાબ database માં નોંધાય છે. ઉદાહરણ: "આજે બજાર કેવું છે?", "v2 નું અત્યાર સુધીનું '
                           'પરિણામ સમજાવો", "M2 ક્યારે શરૂ થશે?", "કયા શેરમાં સૌથી વધુ નુકસાન છે?"</div>')
    hist = st.session_state.setdefault("_g_ask_hist", [])
    q = st.text_area("પ્રશ્ન", key="_g_ask_q", max_chars=ask_garud.MAX_QUESTION_CHARS,
                     placeholder="અહીં પ્રશ્ન લખો…", label_visibility="collapsed")
    if st.button("પૂછો", key="_g_ask_go", use_container_width=True) and ask_garud.clean_question(q):
        try:
            db = _db(settings)
            used = ask_garud.asked_today(db)
        except Exception:
            db, used = None, 0
        if used >= ask_garud.MAX_PER_DAY:
            st.warning(f"આજના {ask_garud.MAX_PER_DAY} પ્રશ્નો પૂરા થયા — કાલે ફરી પૂછો.")
        else:
            with st.spinner("Garud આંકડા જોઈ રહ્યું છે…"):
                rec = ask_garud.ask(q, ask_context(settings, key), AIReasoningEngine()._call_gemini,
                                    [(h["question"], h["answer"]) for h in hist])
            if rec["ok"]:
                if db is not None:
                    try:
                        ask_garud.save(db, rec)
                    except Exception:
                        pass
                hist.append({"question": rec["question"], "answer": rec["answer"], "at": datetime.now(IST).strftime("%H:%M")})
            else:
                st.warning("AI unavailable — " + str(rec.get("error")))
    for h in reversed(hist[-6:]):
        card(f'❓ {_e(h["question"])}',
             f'<div style="white-space:pre-wrap">{_e(h["answer"])}</div>'
             f'<div class="g-s" style="margin-top:6px">{h["at"]} IST · {ask_garud.PROMPT_VERSION}</div>')
