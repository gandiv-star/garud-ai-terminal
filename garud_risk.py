"""Risk Center and execution data for the Garud app — computed from the database and
last prices; read-only. Paper, sandbox and live are always kept separate."""
from datetime import date

CAPITAL_PER_RULE = 100000.0
STOP_NEAR_PCT = 2.0

# NIFTY 50 (+ v1's DLF) by broad sector, for concentration only (approximate NSE industry groups).
SECTOR = {
    "HDFCBANK": "Banks", "ICICIBANK": "Banks", "SBIN": "Banks", "AXISBANK": "Banks", "KOTAKBANK": "Banks",
    "BAJFINANCE": "Financials", "BAJAJFINSV": "Financials", "SHRIRAMFIN": "Financials", "JIOFIN": "Financials",
    "HDFCLIFE": "Financials", "SBILIFE": "Financials", "BSE": "Financials",
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "TECHM": "IT", "WIPRO": "IT",
    "MARUTI": "Auto", "M&M": "Auto", "BAJAJ-AUTO": "Auto", "EICHERMOT": "Auto", "TMPV": "Auto",
    "SUNPHARMA": "Pharma & Health", "DRREDDY": "Pharma & Health", "CIPLA": "Pharma & Health",
    "APOLLOHOSP": "Pharma & Health", "MAXHEALTH": "Pharma & Health",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "TATACONSUM": "FMCG",
    "ASIANPAINT": "Consumer", "TITAN": "Consumer", "TRENT": "Consumer", "ETERNAL": "Consumer",
    "TATASTEEL": "Metals & Mining", "HINDALCO": "Metals & Mining", "JSWSTEEL": "Metals & Mining",
    "COALINDIA": "Metals & Mining", "ADANIENT": "Metals & Mining",
    "RELIANCE": "Energy & Power", "ONGC": "Energy & Power", "NTPC": "Energy & Power", "POWERGRID": "Energy & Power",
    "LT": "Capital Goods & Infra", "BEL": "Capital Goods & Infra", "ADANIPORTS": "Capital Goods & Infra",
    "ULTRACEMCO": "Cement", "GRASIM": "Cement", "BHARTIARTL": "Telecom", "INDIGO": "Services", "DLF": "Realty",
}


def paper_exposure(open_trades: list, prices: dict) -> dict:
    """open_trades: dicts with rule, symbol, entry, stop, qty. Values at entry price; risk from
    the current price to the stop (0 if the price is already below the stop)."""
    by_rule, by_sector, by_symbol, stops = {}, {}, {}, []
    total = risk = unreal = 0.0
    for t in open_trades:
        val = t["entry"] * t["qty"]
        p = prices.get(t["symbol"])
        r = max((p if p else t["entry"]) - t["stop"], 0) * t["qty"]
        total += val
        risk += r
        by_rule[t["rule"]] = by_rule.get(t["rule"], 0) + val
        sec = SECTOR.get(t["symbol"], "Other")
        by_sector[sec] = by_sector.get(sec, 0) + val
        by_symbol[t["symbol"]] = by_symbol.get(t["symbol"], 0) + val
        if p:
            unreal += (p - t["entry"]) * t["qty"]
            dist = (p / t["stop"] - 1) * 100
            stops.append((t["symbol"], t["rule"], p, t["stop"], round(dist, 1)))
    stops.sort(key=lambda x: x[4])
    return {"total": round(total, 2), "open_risk": round(risk, 2), "unrealised": round(unreal, 2),
            "by_rule": by_rule, "by_sector": dict(sorted(by_sector.items(), key=lambda kv: -kv[1])),
            "multi_rule_symbols": {s: v for s, v in by_symbol.items()
                                   if sum(1 for t in open_trades if t["symbol"] == s) > 1},
            "stops": stops, "near_stop": [s for s in stops if s[4] <= STOP_NEAR_PCT],
            "priced": sum(1 for t in open_trades if prices.get(t["symbol"])), "count": len(open_trades)}


def drawdown(closed_pnls_in_order: list) -> tuple[float, float]:
    """(max drawdown in rupees from the running peak of cumulative realised P&L, current drawdown)."""
    cum = peak = 0.0
    mdd = 0.0
    for p in closed_pnls_in_order:
        cum += p
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)
    return round(mdd, 2), round(peak - cum, 2)


def month_realised(closed: list, today: date) -> float:
    return round(sum(t["pnl"] for t in closed if t["exit_date"] and (t["exit_date"].year, t["exit_date"].month)
                     == (today.year, today.month)), 2)


def sandbox_status(expected_ids: set, ok_events: list, failed_events: list) -> dict:
    done = {(e or {}).get("internal_order_id") for e in ok_events}
    failed_ids = {(e or {}).get("internal_order_id") for e in failed_events} - done
    return {"expected": len(expected_ids), "placed": len(expected_ids & done),
            "missing": sorted(expected_ids - done), "failed": sorted(failed_ids & expected_ids),
            "last": ok_events[:5]}
