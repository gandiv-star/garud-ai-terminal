"""Research Lab data for the Garud app — every number comes from a stored test result in the
database (never typed in). A test that was never run is shown as NOT RUN / NOT TESTED."""
from datetime import timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
STUDIES = ("TAX_STUDY", "ML_LAB", "M2_ROBUSTNESS", "SWING2_15Y", "MOMENTUM_200", "PORTFOLIO_15Y", "EVIDENCE_MATRIX", "LONGTERM_COMPARISON", "LONGTERM_15Y", "INTRADAY_TEST")
SAME_ASSUMPTIONS = ("Same engine for every strategy: entry at the next day's open, stop 2×ATR, "
                    "1% risk of ₹1,00,000 per trade, real delivery charges (STT, exchange, stamp, GST); "
                    "intraday and options tests use their own real cost models.")


def _when(ev):
    ts = ev.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(IST)


def latest_studies(db) -> dict:
    out = {}
    for kind in STUDIES:
        evs = db.get_audit_events(kind, limit=1)
        out[kind] = (_when(evs[0]), evs[0].payload or {}) if evs else None
    return out


# ------------------------------------------------------------------ per-study summaries
def evidence_summary(p: dict) -> dict:
    sel, base = p.get("selection_test") or {}, p.get("baseline_test") or {}
    ok = bool(p.get("mode_has_evidence"))
    return {"title": "Regime પ્રમાણે strategy પસંદગી (Evidence matrix)", "pass": ok,
            "verdict": "પુરાવો મળ્યો" if ok else "પુરાવો નથી",
            "lines": [("Train / test trades", f'{p.get("train_trades", "—")} / {p.get("test_trades", "—")}'),
                      ("Favoured → confirmed cells", f'{p.get("favoured_cells", "—")} → {p.get("confirmed_cells", "—")}'),
                      ("Test PF: પસંદગી vs બધા", f'{sel.get("pf", "—")} vs {base.get("pf", "—")}'),
                      ("Test avg/trade: પસંદગી vs બધા", f'₹{sel.get("avg", "—")} vs ₹{base.get("avg", "—")}'),
                      ("Out-of-sample split", str(p.get("split_date", "—"))),
                      ("Version", f'v{p.get("version", 1)} · fills: {(p.get("fill_model") or {}).get("name", "legacy")}'
                                  + (" · RS bug fixed" if (p.get("version") or 1) >= 2 else " · RS bug હતો (જૂનું)"))]}


def longterm_rows(p: dict) -> list:
    """[(strategy, full cagr, full maxdd, test/last cagr, trades, candidate or None)]"""
    verd = p.get("verdicts") or {}
    out = []
    for r in p.get("rows") or []:
        f, t = r.get("full") or {}, r.get("test") or {}
        k = (r.get("strategy") or "?")[0]
        cand = (verd.get(k) or {}).get("candidate") if verd else r.get("candidate")
        out.append((r.get("strategy"), f.get("cagr"), f.get("max_dd"), t.get("cagr"), r.get("trades"), cand))
    return out


BIASED = ("D", "E")   # momentum on TODAY's NIFTY 50 list (survivorship bias) — shown for comparison only


def longterm_summary(p: dict, label: str, eligible: str) -> dict:
    """eligible: strategy letters whose verdict counts under that study's pre-registration
    (15-year check: F and G only; D/E use today's list and can never be candidates)."""
    rows = longterm_rows(p)
    cands = [r[0] for r in rows if r[5] and (r[0] or "?")[0] in eligible and (r[0] or "?")[0] not in BIASED]
    return {"title": label, "pass": bool(cands),
            "verdict": ("Candidate: " + ", ".join(cands)) if cands else "કોઈ candidate નથી",
            "lines": [(r[0] + (" — biased list, માત્ર સરખામણી" if (r[0] or "?")[0] in BIASED else ""),
                       f'{r[1]}% (DD {r[2]}%) · પાછલો ભાગ {r[3]}%') for r in rows],
            "period": f'{p.get("start", "—")} → {p.get("end", "—")}'}


def intraday_summary(p: dict) -> dict:
    st = p.get("strategies") or {}
    passed = [k for k, v in st.items() if v.get("pass")]
    return {"title": "Intraday (NIFTY 50, 60-min, 2 વર્ષ)", "pass": bool(passed),
            "verdict": ("PASS: " + ", ".join(passed)) if passed else "કોઈ પાસ નથી",
            "lines": [(k, f'PF {v.get("all", {}).get("pf", "—")} · avg ₹{v.get("all", {}).get("avg", "—")} '
                          f'(ખર્ચ પહેલાં ₹{v.get("all", {}).get("gross_avg", "—")})') for k, v in st.items()],
            "period": f'{p.get("first_date", "—")} → {p.get("last_date", "—")}'}


def momentum_paper_rows(rebals: list, navs: list, names: dict, capital=100000.0) -> list:
    """Forward paper portfolios. rebals/navs: event payloads (any order). One dict per portfolio."""
    base = [p for p in navs if p.get("nifty")]
    base_nifty = min(base, key=lambda p: p["date"])["nifty"] if base else None
    out = []
    for pid, name in names.items():
        mine = sorted((p for p in rebals if p.get("portfolio") == pid), key=lambda p: p.get("fill_date") or "")
        nv = sorted((p for p in navs if p.get("portfolio") == pid), key=lambda p: p["date"])
        if not mine:
            out.append({"id": pid, "name": name, "started": False})
            continue
        cap = float(capital.get(pid, 100000.0) if isinstance(capital, dict) else capital)
        last, latest = mine[-1], (nv[-1] if nv else {"value": mine[-1]["value"], "date": mine[-1]["fill_date"]})
        peak, dd = cap, 0.0
        for p in nv:
            peak = max(peak, p["value"])
            dd = max(dd, (peak - p["value"]) / peak * 100)
        out.append({"id": pid, "name": name, "started": True, "value": latest["value"], "date": latest["date"],
                    "ret": round((latest["value"] / cap - 1) * 100, 2), "capital": cap,
                    "nifty_ret": (round((latest["nifty"] / base_nifty - 1) * 100, 2)
                                  if latest.get("nifty") and base_nifty else None),
                    "max_dd": round(dd, 2), "rebalances": len(mine), "last_fill": last.get("fill_date"),
                    "weak": bool(last.get("weak_market")), "cash": last.get("cash"),
                    "holdings": sorted((last.get("units") or {}).items())})
    return out


def tax_study_summary(p: dict) -> dict:
    rows = p.get("rows") or []
    lines = [(str(r.get("strategy")),
              f'tax પહેલાં {r.get("pre_tax_cagr", "—")}% → tax પછી {r.get("after_tax_cagr", "—")}% વર્ષે · '
              f'કુલ tax ₹{(r.get("tax_paid") or 0):,.0f} · હાથમાં ₹{(r.get("final_after_tax") or 0):,.0f}')
             for r in rows]
    lines.append(("ધારણા", "કુલ આવક ₹12 લાખ સુધી: FD/liquid પર tax નહીં · શેર: short 20%, long 12.5% "
                           "(₹1.25 લાખ ઉપર) · આજના નિયમ બધા વર્ષે · CA પાસે ખાતરી કરો"))
    win = [r["strategy"] for r in rows[1:] if r.get("beats_fd_after_tax")]
    return {"title": f'Tax પછીનું વળતર (₹{(p.get("capital") or 0):,.0f}, 15 વર્ષ)', "pass": bool(win),
            "verdict": ("Tax પછી પણ FD થી વધુ: " + ", ".join(win)) if win else "Tax પછી કોઈ FD થી આગળ નથી",
            "lines": lines, "period": f'{p.get("start", "—")} → {p.get("end", "—")}'}


def ml_lab_summary(p: dict) -> dict:
    rows = p.get("rows") or []
    lines = [(str(r.get("strategy")), f'{(r.get("full") or {}).get("cagr", "—")}% વર્ષે · ઘટાડો '
                                     f'{(r.get("full") or {}).get("max_dd", "—")}%') for r in rows]
    if p.get("top_quintile_hit_rate") is not None:
        lines.append(("ML ની પસંદગી સરેરાશ શેરથી સારી", f'{p["top_quintile_hit_rate"]}% મહિનામાં'))
    adopt = bool(p.get("adopt_ml"))
    return {"title": "AI/ML Lab — ML picker vs M2 નિયમ", "pass": adopt,
            "verdict": "ML અપનાવવા લાયક" if adopt else "M2 નિયમ જ સારો (ML અપનાવ્યું નથી)",
            "lines": lines, "period": f'{p.get("start", "—")} → {p.get("end", "—")}'}


def m2_robustness_summary(p: dict) -> dict:
    rows = p.get("rows") or []
    lines = [(("✅ " if (r.get("verdict") or {}).get("pass") else "❌ ") + str(r.get("strategy")),
              f'{(r.get("full") or {}).get("cagr", "—")}% વર્ષે · ઘટાડો {(r.get("full") or {}).get("max_dd", "—")}% · '
              f'Sharpe {r.get("sharpe", "—")}') for r in rows]
    b = p.get("bootstrap") or {}
    if b.get("p_below_fd") is not None:
        lines.append(("Bootstrap", f'FD થી ઓછું આવવાની શક્યતા {b["p_below_fd"]}% · 5મો percentile {b["cagr_p5"]}%'))
    for x in p.get("benchmarks") or []:
        if x.get("available"):
            lines.append((x["name"], f'{x["cagr"]}% વર્ષે vs M2 {x["m2_cagr_same_period"]}% ({x["from"]}→{x["to"]})'))
    robust = bool(p.get("robust"))
    return {"title": "M2 મજબૂતી ચકાસણી (6 settings)", "pass": robust,
            "verdict": f'{"મજબૂત" if robust else "નાજુક"}: {p.get("passed_count", "—")}/6 પાસ',
            "lines": lines, "period": f'{p.get("start", "—")} → {p.get("end", "—")}'}


def swing2_summary(p: dict) -> dict:
    c = portfolio_summary(p)
    c["title"] = "Engine 2 — Swing 2.0 (મજબૂત શેરમાં ઘટાડે ખરીદી, 15 વર્ષ)"
    c["pass"] = bool(p.get("chosen"))
    c["verdict"] = ("Paper માટે પસંદ: " + p["chosen"]) if p.get("chosen") else "S50 માં કોઈ પાસ નથી"
    c["lines"].append(("નોંધ", "S50 = સાચું NIFTY 50 લિસ્ટ (નિર્ણય આના પરથી) · S200 = આજનું લિસ્ટ, માત્ર માહિતી"))
    return c


def momentum200_summary(p: dict) -> dict:
    c = portfolio_summary(p)
    c["title"] = "Engine 1 — Momentum 200 (15 વર્ષ, ₹1 લાખ)"
    c["lines"].append(("⚠️ નોંધ", "આજનું NIFTY 200 લિસ્ટ વપરાયું — પરિણામ થોડું વધુ સારું દેખાય"))
    return c


def portfolio_summary(p: dict) -> dict:
    """Phase 2: one shared account, 15 years. PASS = CAGR > 7% and max drawdown <= 25%."""
    passed = p.get("passed") or []
    lines = []
    for r in p.get("rows") or []:
        f, v = r.get("full") or {}, r.get("verdict")
        mark = ("" if v is None else " ✅ PASS" if v.get("pass") else " ❌")
        lines.append((f'{r.get("strategy", "?")}{mark}',
                      f'{f.get("cagr", "—")}% વર્ષે · ઘટાડો {f.get("max_dd", "—")}% · '
                      f'₹{(f.get("final") or 0):,.0f}'))
    return {"title": "Phase 2 — 15 વર્ષ, એક જ ₹1 લાખ ખાતું", "pass": bool(passed),
            "verdict": ("Paper માટે પસંદ: " + ", ".join(passed)) if passed else "કોઈ પાસ નથી",
            "lines": lines, "period": f'{p.get("start", "—")} → {p.get("end", "—")}'}


def study_cards(studies: dict) -> list:
    """[(kind, when or None, summary dict or None)] in a fixed order."""
    makers = {"TAX_STUDY": tax_study_summary,
              "ML_LAB": ml_lab_summary,
              "M2_ROBUSTNESS": m2_robustness_summary,
              "SWING2_15Y": swing2_summary,
              "MOMENTUM_200": momentum200_summary,
              "PORTFOLIO_15Y": portfolio_summary,
              "EVIDENCE_MATRIX": evidence_summary,
              "LONGTERM_COMPARISON": lambda p: longterm_summary(p, "લાંબા ગાળાની સરખામણી (5 વર્ષ)", "CFG"),
              "LONGTERM_15Y": lambda p: longterm_summary(p, "15 વર્ષ (સાચું NIFTY 50 લિસ્ટ)", "FG"),
              "INTRADAY_TEST": intraday_summary}
    out = []
    for kind in STUDIES:
        item = studies.get(kind)
        if not item:
            out.append((kind, None, None))
            continue
        when, payload = item
        try:
            out.append((kind, when, makers[kind](payload)))
        except Exception as e:
            out.append((kind, when, {"title": kind, "pass": False, "verdict": f"read error: {e}", "lines": []}))
    return out


# ------------------------------------------------------------------ rules: backtest vs paper
def rule_rows(rules, trades: list, benches: dict, checkpoint_status) -> list:
    """trades: dicts with rule, exit, pnl, exit_date (garud_mobile.load_trades rows)."""
    out = []
    for r in rules:
        closed = sorted([t for t in trades if t["rule"] == r.rule_id and t["exit"] is not None and t["pnl"] is not None],
                        key=lambda t: t["exit_date"])
        pnls = [t["pnl"] for t in closed]
        wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p <= 0]
        b = benches.get(r.rule_id) or {}
        try:
            status = checkpoint_status(pnls, b or None)
        except Exception:
            status = "—"
        out.append({
            "title": r.title, "strategy": r.strategy_name, "describe": r.describe(),
            "bench": ({"trades": b.get("trades"), "avg": b.get("mean"), "win": b.get("win_rate"), "pf": b.get("pf"),
                       "period": b.get("period")} if b else None),
            "paper": {"closed": len(pnls), "target": r.target_trades, "net": round(sum(pnls), 2),
                      "avg": round(sum(pnls) / len(pnls), 2) if pnls else None,
                      "win": round(len(wins) / len(pnls) * 100, 1) if pnls else None,
                      "pf": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None},
            "status": status,
        })
    return out


def registry_rows(registry: dict, rules, strategy_regimes) -> list:
    used = {}
    for r in rules:
        used.setdefault(r.strategy_name, []).append(r.title)
    out = []
    for name in registry:
        regs = strategy_regimes(name)
        out.append({"name": name, "rules": used.get(name, []),
                    "status": "Paper test ચાલુ" if name in used else "માત્ર research",
                    "regimes": "બધા" if len(regs) >= 7 else ", ".join(sorted(regs))})
    return out
