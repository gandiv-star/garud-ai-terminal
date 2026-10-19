"""Engine 1 — Momentum on a NIFTY 200-sized universe (bull-market engine of the Trading Mode plan).

Pre-registered 19 Oct 2026, before running. 15 years ending rule_report.BENCHMARK_END, one shared
Rs.1,00,000 account, real delivery charges, idle money at the liquid-fund rate (6.5%).

Universe each month-end (reduces, but cannot remove, survivorship bias):
  candidates = today's NIFTY 200 list + every stock ever in the NIFTY 50 since 2010
  eligible   = at least 1 year of prices, then the 150 most liquid by average traded value
               (close x volume) over the last 6 months — i.e. roughly "the NIFTY 200 of that day"
Score (NSE Momentum-index style): 6-month and 12-month returns, each divided by the stock's
  1-year volatility, turned into z-scores across eligible stocks and averaged.
Portfolio: top 20, equal weight, rebalanced every month-end (trade at the next day's close);
  a stock already held is kept while it stays inside the top 30 (lower turnover and tax).
Variants:
  M1  Momentum 200
  M2  M1 + weak-market switch: when NIFTY's regime is not MODERATE_BULL/WEAK_BULL at the
      month-end, hold the liquid fund instead (owner's idea, 19 Oct 2026)
  G   NIFTY 50 point-in-time momentum + switch (the earlier Phase 2 pass), same data, for comparison
PASS = 15-year CAGR > 7% (FD) AND max drawdown <= 25%. Beating NIFTY buy & hold is reported.
Honesty: today's NIFTY 200 list contains stocks that grew INTO the index, and companies that later
collapsed or delisted are partly missing — the M results are therefore optimistic. A PASS means
"worth paper trading", never "profitable".
"""
import math
from bisect import bisect_right
from datetime import date, datetime, timedelta

from backtest import longterm as lt
from backtest.backtest_engine import _nifty_series

VERSION = 1
NIFTY200_TODAY = (
    "360ONE", "ABB", "APLAPOLLO", "AUBANK", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER",
    "ATGL", "ABCAPITAL", "AMBUJACEM", "APARINDS", "APOLLOHOSP", "ASHOKLEY", "ASIANPAINT", "ASTRAL", "AUROPHARMA",
    "DMART", "AXISBANK", "BSE", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BAJAJHLDNG", "BANKBARODA", "BANKINDIA",
    "MAHABANK", "BDL", "BEL", "BHARATFORG", "BHEL", "BPCL", "BHARTIARTL", "GROWW", "BIOCON", "BLUESTARCO",
    "BOSCHLTD", "BRITANNIA", "CGPOWER", "CANBK", "CHOLAFIN", "CIPLA", "COALINDIA", "COCHINSHIP", "COFORGE",
    "COLPAL", "CONCOR", "CUMMINSIND", "DLF", "DABUR", "DIVISLAB", "DIXON", "DRREDDY", "EICHERMOT", "ETERNAL",
    "EXIDEIND", "NYKAA", "FEDERALBNK", "FORTIS", "GAIL", "GVT&D", "GMRAIRPORT", "GLENMARK", "GODFRYPHLP",
    "GODREJCP", "GODREJPROP", "GRASIM", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HAVELLS", "HEROMOTOCO",
    "HINDALCO", "HAL", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "HINDZINC", "POWERINDIA", "HYUNDAI", "ICICIBANK",
    "ICICIGI", "ICICIAMC", "IDFCFIRSTB", "ITC", "INDIANB", "INDHOTEL", "IOC", "IRCTC", "IRFC", "IREDA",
    "INDUSTOWER", "INDUSINDBK", "NAUKRI", "INFY", "INDIGO", "JSWENERGY", "JSWSTEEL", "JINDALSTEL", "JIOFIN",
    "JUBLFOOD", "KEI", "KALYANKJIL", "KOTAKBANK", "LTF", "LGEINDIA", "LICHSGFIN", "LTM", "LT", "LAURUSLABS",
    "LENSKART", "LICI", "LODHA", "LUPIN", "MRF", "M&MFIN", "M&M", "MANKIND", "MARICO", "MARUTI", "MFSL",
    "MAXHEALTH", "MAZDOCK", "MEESHO", "MOTILALOFS", "MPHASIS", "MCX", "MUTHOOTFIN", "NHPC", "NLCINDIA", "NMDC",
    "NTPC", "NATIONALUM", "NESTLEIND", "OBEROIRLTY", "ONGC", "OIL", "PAYTM", "OFSS", "POLICYBZR", "PIIND",
    "PAGEIND", "PATANJALI", "PERSISTENT", "PHOENIXLTD", "PIDILITIND", "POLYCAB", "PFC", "POWERGRID",
    "PREMIERENE", "PRESTIGE", "PNB", "RECLTD", "RADICO", "RVNL", "RELIANCE", "SBICARD", "SBILIFE", "SRF",
    "MOTHERSON", "SHRIRAMFIN", "ENRIN", "SIEMENS", "SOLARINDS", "SBIN", "SAIL", "SUNPHARMA", "SUPREMEIND",
    "SUZLON", "SWIGGY", "TVSMOTOR", "TATACAP", "TATACOMM", "TCS", "TATACONSUM", "TMCV", "TMPV", "TATAPOWER",
    "TATASTEEL", "TECHM", "TITAN", "TORNTPHARM", "TRENT", "TIINDIA", "UPL", "ULTRACEMCO", "UNIONBANK",
    "UNITDSPR", "VBL", "VAML", "VEDL", "VMM", "IDEA", "VOLTAS", "WAAREEENER", "WIPRO", "YESBANK", "ZYDUSLIFE",
)   # NSE ind_nifty200list.csv, fetched 19 Oct 2026
LIQUID_TOP, TOP_N, KEEP_RANK = 150, 20, 30
R6, R12, VALUE_DAYS, MIN_HISTORY = 126, 252, 126, 230
PASS_CAGR, PASS_MAX_DD = 7.0, 25.0
EVAL_DAYS = 15 * 365 + 4
DECADE_DAYS = 10 * 365 + 2


def _d(ts):
    return ts.date() if hasattr(ts, "date") else ts


class Data:
    """Closes (via longterm.Market: forward-filled, bad ticks removed) + daily traded value."""

    def __init__(self, nifty: list, bars: dict):
        closes = {s: {_d(b.timestamp): float(b.close) for b in bl} for s, bl in bars.items()}
        self.mkt = lt.Market(nifty, closes)
        pos = {d: i for i, d in enumerate(self.mkt.dates)}
        self.value = {}
        for s, bl in bars.items():
            v = [0.0] * len(self.mkt.dates)
            for b in bl:
                i = pos.get(_d(b.timestamp))
                if i is not None:
                    v[i] = float(b.close) * float(b.volume or 0)
            self.value[s] = v

    def avg_value(self, s, i, n=VALUE_DAYS):
        v = self.value.get(s)
        if not v or i < n:
            return 0.0
        return sum(v[i - n + 1: i + 1]) / n

    def score_inputs(self, s, i):
        """(6m/vol, 12m/vol) or None when history is too short."""
        if i < R12:
            return None
        px = [self.mkt.price(s, k) for k in range(i - R12, i + 1)]
        if sum(1 for p in px if p) < MIN_HISTORY:
            return None
        p_now, p6, p12 = px[-1], px[-1 - R6], px[0]
        if not (p_now and p6 and p12):
            return None
        rets = [math.log(b / a) for a, b in zip(px[:-1], px[1:]) if a and b]
        if len(rets) < MIN_HISTORY - 1:
            return None
        mean = sum(rets) / len(rets)
        vol = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)) * math.sqrt(252)
        if vol <= 0:
            return None
        return (p_now / p6 - 1) / vol, (p_now / p12 - 1) / vol


def ranking(data: Data, i: int, candidates) -> list:
    """Eligible stocks ranked best first by the NSE-style momentum score."""
    pool = []
    for s in candidates:
        if s == lt.ETF or not data.mkt.price(s, i):
            continue
        si = data.score_inputs(s, i)
        if si:
            pool.append((data.avg_value(s, i), s, si))
    pool.sort(reverse=True)
    pool = pool[:LIQUID_TOP]
    if len(pool) < TOP_N:
        return [s for _, s, _ in pool]

    def z(vals):
        m = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals)) or 1.0
        return [(v - m) / sd for v in vals]

    z6, z12 = z([p[2][0] for p in pool]), z([p[2][1] for p in pool])
    scored = sorted(((a + b) / 2, p[1]) for a, b, p in zip(z6, z12, pool))
    return [s for _, s in reversed(scored)]


def momentum_targets(data: Data, candidates_fn, weak_switch: bool):
    held = set()

    def target(i):
        nonlocal held
        if weak_switch and not data.mkt.regime_bull(i):
            held = set()
            return {}
        ranked = ranking(data, i, candidates_fn(data.mkt.dates[i]))
        keep = [s for s in ranked[:KEEP_RANK] if s in held]
        picks = keep + [s for s in ranked if s not in keep][: max(0, TOP_N - len(keep))]
        held = set(picks)
        return {s: 1.0 / TOP_N for s in picks} if picks else {}
    return target


def verdict(full: dict) -> dict:
    cagr, dd = full.get("cagr"), full.get("max_dd")
    beats_fd = cagr is not None and cagr > PASS_CAGR
    dd_ok = dd is not None and dd <= PASS_MAX_DD
    return {"beats_fd": beats_fd, "dd_ok": dd_ok, "pass": beats_fd and dd_ok}


def load(symbols, end_date: date, aliases: dict, loader=None, nifty=None, eval_days: int = EVAL_DAYS):
    from backtest import portfolio15 as pf
    end = datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)
    eval_start = end - timedelta(days=eval_days)
    data_start = eval_start - timedelta(days=lt.LOOKBACK_DAYS)
    if nifty is None:
        nifty = _nifty_series(data_start, end)
    if loader is None:
        from data.yfinance_loader import YFinanceLoader
        loader = YFinanceLoader()
    bars, errors = {}, {}
    for sym in list(dict.fromkeys(list(symbols) + [lt.ETF])):
        try:
            bl = loader.get_historical_bars(sym, data_start, end)
        except Exception as e:
            bl, err = [], str(e)
        else:
            err = None
        for alt in aliases.get(sym, ()):
            if bl and _d(bl[0].timestamp) <= _d(data_start) + timedelta(days=30):
                break
            try:
                alt_bl = loader.get_historical_bars(alt, data_start, end)
            except Exception:
                alt_bl = []
            if alt_bl:
                bl = pf.stitch_bars(bl, alt_bl)
        if bl:
            bars[sym] = pf.clean_bars(bl)
        else:
            errors[sym] = (err or "no data")[:120]
    if lt.ETF not in bars:
        errors[lt.ETF] = "NIFTYBEES unavailable — used ^NSEI price index"
    data = Data(nifty, bars)
    if lt.ETF not in bars:
        data.mkt.px[lt.ETF] = list(data.mkt.nifty)
    return data, eval_start.date(), errors


def run(data: Data, eval_start: date, candidates_fn, nifty50_members_fn) -> dict:
    mkt = data.mkt
    start_i = max(bisect_right(mkt.dates, eval_start) - 1, 0)
    start, end = mkt.dates[start_i], mkt.dates[-1]
    split = start + timedelta(days=DECADE_DAYS)
    rebal = [start_i - 1] + lt.month_end_indices(mkt.dates, start_i)
    rebal = [i for i in rebal if i >= 0]
    sim_start = min([start_i] + [i + 1 for i in rebal])

    def one(name, fn, idx):
        curve, n = lt.simulate(mkt, sim_start, fn, idx)
        w = lt._windows(curve, start, split, end)
        return {"strategy": name, **w, "yearly": lt.yearly(curve), "trades": n}

    rows = []
    fd = [(d, lt.CAPITAL * (1 + lt.FD_RATE) ** ((d - start).days / 365)) for d in mkt.dates[start_i:]]
    rows.append({"strategy": "FD 7%", **lt._windows(fd, start, split, end), "yearly": lt.yearly(fd), "trades": 0})
    rows.append(one("NIFTY buy & hold", lambda i: {lt.ETF: 1.0}, rebal[:1]))
    for name, switch in (("M1 Momentum 200", False), ("M2 Momentum 200 + weak-market switch", True)):
        r = one(name, momentum_targets(data, candidates_fn, switch), rebal)
        r["verdict"] = verdict(r["full"])
        rows.append(r)

    def g_target(i):
        if not mkt.regime_bull(i):
            return {}
        pool = [s for s in nifty50_members_fn(mkt.dates[i]) if s in mkt.px and s != lt.ETF]
        scored = sorted(((m, s) for s in pool if (m := mkt.momentum(s, i)) is not None and mkt.price(s, i)),
                        reverse=True)
        return {s: 1.0 / lt.TOP_N for _, s in scored[: lt.TOP_N]}
    g = one("G NIFTY 50 momentum + switch (earlier pass)", g_target, rebal)
    g["verdict"] = verdict(g["full"])
    rows.append(g)
    bh = rows[1]
    for r in rows:
        if "verdict" in r:
            r["verdict"]["beats_nifty"] = (r["full"]["cagr"] or -99) > (bh["full"]["cagr"] or -99)
    passed = [r["strategy"] for r in rows if (r.get("verdict") or {}).get("pass")]
    return {"version": VERSION, "registered": "2026-10-19", "start": str(start), "split": str(split),
            "end": str(end), "years": round((end - start).days / 365, 2), "rows": rows, "passed": passed,
            "rules": {"universe": f"today's NIFTY 200 + all NIFTY 50 members since 2010, top {LIQUID_TOP} by liquidity",
                      "top_n": TOP_N, "keep_rank": KEEP_RANK, "rebalance": "monthly",
                      "pass_cagr_gt": PASS_CAGR, "pass_max_dd_le": PASS_MAX_DD, "liquid_rate": lt.LIQUID_RATE},
            "bias_note": "today's NIFTY 200 list: survivorship bias — results optimistic"}
