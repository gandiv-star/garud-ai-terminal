"""After-tax comparison: M2 vs G vs NIFTY ETF vs FD for the owner's tax situation.

Owner's answer (21 Oct 2026): total yearly income up to Rs.12 lakh (new regime) -> FD interest and
liquid-fund returns are effectively tax-free (Sec. 87A rebate), but the rebate does not cover
equity capital gains taxed at special rates. Today's rules are applied to all 15 years
(a "what if these rules had always applied" view), as known on 21 Oct 2026 — confirm with a CA:
  * short-term (held <= 12 months) equity gains: 20%
  * long-term (held > 12 months) equity gains: 12.5% on the part above Rs.1,25,000 per financial year
  * set-off: a short-term loss can offset short- or long-term gains; a long-term loss only
    long-term gains; unused losses carry forward
  * tax is paid from the account at each financial-year end (April); at the end of the period
    everything is valued as if sold and the tax on that sale is deducted ("money in hand")
  * no tax on FD interest or liquid-fund returns at this income level; STT and other charges are
    already in the trading costs
Same trading rules, data and costs as Engine 1 (backtest/momentum200.py) / longterm.simulate.
Information only — not tax advice.
"""
from bisect import bisect_right
from datetime import date

from backtest import longterm as lt
from backtest import momentum200 as m2
from backtest.backtest_engine import ChargeModel

VERSION = 1
CAPITAL = 300000.0   # the M2 paper amount; tax depends on size (Rs.1.25L LTCG exemption)
STCG, LTCG, LTCG_EXEMPT = 0.20, 0.125, 125000.0


def fy_of(d: date) -> int:
    return d.year if d.month >= 4 else d.year - 1


class TaxBook:
    """FIFO lots per symbol, realised gains per financial year, losses carried forward."""

    def __init__(self):
        self.lots = {}          # sym -> [[units, cost_per_unit, buy_date]]
        self.st = self.lt = 0.0
        self.st_carry = self.lt_carry = 0.0
        self.paid = 0.0

    def buy(self, sym, units, cost_per_unit, day):
        self.lots.setdefault(sym, []).append([units, cost_per_unit, day])

    def sell(self, sym, units, proceeds_per_unit, day):
        lots = self.lots.get(sym, [])
        while units > 1e-12 and lots:
            lot = lots[0]
            take = min(units, lot[0])
            gain = take * (proceeds_per_unit - lot[1])
            if (day - lot[2]).days > 365:
                self.lt += gain
            else:
                self.st += gain
            lot[0] -= take
            units -= take
            if lot[0] <= 1e-12:
                lots.pop(0)

    @staticmethod
    def _net(st: float, ltg: float) -> tuple:
        """(taxable st, taxable lt, st loss left, lt loss left). A short-term loss may offset
        long-term gains; a long-term loss only long-term gains."""
        st_left = lt_left = 0.0
        if st < 0:
            use = min(-st, max(ltg, 0.0))
            ltg -= use
            st_left, st = -st - use, 0.0
        if ltg < 0:
            lt_left, ltg = -ltg, 0.0
        return st, ltg, st_left, lt_left

    @staticmethod
    def _tax(st: float, ltg: float) -> float:
        return st * STCG + max(ltg - LTCG_EXEMPT, 0.0) * LTCG

    def settle(self) -> float:
        """Tax for the financial year just ended; resets the year's gains, carries losses forward."""
        st, ltg, self.st_carry, self.lt_carry = self._net(self.st - self.st_carry, self.lt - self.lt_carry)
        tax = self._tax(st, ltg)
        self.st = self.lt = 0.0
        self.paid += tax
        return tax

    def unrealised_tax(self, prices: dict, day: date) -> float:
        """Tax if everything were sold at `prices` on `day` (added to this year's gains)."""
        st, ltg = self.st, self.lt
        for sym, lots in self.lots.items():
            p = prices.get(sym)
            if not p:
                continue
            for u, c, d in lots:
                if (day - d).days > 365:
                    ltg += u * (p - c)
                else:
                    st += u * (p - c)
        st, ltg, _, _ = self._net(st - self.st_carry, ltg - self.lt_carry)
        return self._tax(st, ltg)


def simulate_taxed(mkt, start_i: int, target_fn, rebalance_idx: list, taxed: bool = True,
                   capital: float = lt.CAPITAL) -> dict:
    """longterm.simulate (same trades and costs) plus tax lots; taxed=False reproduces it exactly.
    Yearly tax is paid from cash. Returns the curve, tax paid, and the value after a final sale."""
    cm = ChargeModel()
    units, cash = {}, float(capital)
    book = TaxBook()
    pending, trades = None, 0
    targets = {i + 1: i for i in rebalance_idx}
    curve = []
    fy = fy_of(mkt.dates[start_i])
    for i in range(start_i, len(mkt.dates)):
        day = mkt.dates[i]
        if i > start_i:
            cash *= (1 + lt.LIQUID_RATE) ** ((day - mkt.dates[i - 1]).days / 365)
        if taxed and fy_of(day) != fy:
            cash -= book.settle()
            fy = fy_of(day)
        for sym in list(units):
            if mkt.price(sym, i) is None:
                last = next((mkt.price(sym, k) for k in range(i - 1, -1, -1) if mkt.price(sym, k)), 0)
                u = units.pop(sym)
                proceeds = u * last
                fee = cm.sell_charges(proceeds)
                cash += proceeds - fee
                book.sell(sym, u, (proceeds - fee) / u if u else 0, day)
        if i in targets:
            pending = target_fn(targets[i])
        if pending is not None:
            value = cash + sum(u * mkt.price(s, i) for s, u in units.items())
            want = {s: w for s, w in pending.items() if w > 0 and mkt.price(s, i)}
            for s in set(units) | set(want):
                p = mkt.price(s, i)
                cur = units.get(s, 0) * p
                diff = want.get(s, 0) * value - cur
                if diff < 0 and (abs(diff) >= lt.NO_TRADE_BAND * value or s not in want):
                    sell = min(-diff, cur)
                    fee = cm.sell_charges(sell)
                    cash += sell - fee
                    u = sell / p
                    book.sell(s, u, (sell - fee) / u, day)
                    units[s] = units.get(s, 0) - u
                    if units[s] * p < 1:
                        units.pop(s)
                    trades += 1
            buys = {}
            for s, w in want.items():
                p = mkt.price(s, i)
                diff = w * value - units.get(s, 0) * p
                if diff > 0 and (diff >= lt.NO_TRADE_BAND * value or s not in units):
                    buys[s] = diff
            need = sum(buys.values()) * 1.002
            scale = min(1.0, cash / need) if need > 0 else 0.0
            for s, amt in buys.items():
                amt *= scale
                fee = cm.buy_charges(amt)
                if amt <= 0 or amt + fee > cash:
                    continue
                cash -= amt + fee
                u = amt / mkt.price(s, i)
                units[s] = units.get(s, 0) + u
                book.buy(s, u, (amt + fee) / u, day)
                trades += 1
            pending = None
        value = cash + sum(u * mkt.price(s, i) for s, u in units.items())
        curve.append((day, value))
    last_i = len(mkt.dates) - 1
    prices = {s: mkt.price(s, last_i) for s in units}
    exit_tax = book.unrealised_tax(prices, mkt.dates[last_i]) if taxed else 0.0
    sale_cost = sum(cm.sell_charges(u * prices[s]) for s, u in units.items() if prices.get(s))
    in_hand = curve[-1][1] - exit_tax - (sale_cost if taxed else 0.0)
    return {"curve": curve, "trades": trades, "tax_paid": round(book.paid, 2), "exit_tax": round(exit_tax, 2),
            "final_after_tax": round(in_hand, 2)}


def cagr(start_value: float, end_value: float, start: date, end: date):
    days = (end - start).days
    if days <= 0 or start_value <= 0 or end_value <= 0:
        return None
    return round(((end_value / start_value) ** (365 / days) - 1) * 100, 2)


def run(data, eval_start: date, candidates_fn, nifty50_members_fn, capital: float = CAPITAL) -> dict:
    mkt = data.mkt
    start_i = max(bisect_right(mkt.dates, eval_start) - 1, 0)
    start, end = mkt.dates[start_i], mkt.dates[-1]
    rebal = [i for i in [start_i - 1] + lt.month_end_indices(mkt.dates, start_i) if i >= 0]
    sim_start = min([start_i] + [i + 1 for i in rebal])
    years = (end - start).days / 365
    fd_final = capital * (1 + lt.FD_RATE) ** years
    rows = [{"strategy": "FD 7%", "pre_tax_cagr": 7.0, "after_tax_cagr": 7.0, "kept_cagr": 7.0,
             "final_after_tax": round(fd_final), "tax_paid": 0, "max_dd": 0.0, "trades": 0}]
    makers = (("NIFTY ETF buy & hold", lambda: (lambda i: {lt.ETF: 1.0}), rebal[:1]),
              ("M2 Momentum 200", lambda: m2.momentum_targets(data, candidates_fn, True), rebal),
              ("G NIFTY 50 momentum", lambda: (lambda i: m2.g_weights(mkt, i, nifty50_members_fn)), rebal))
    for name, make, idx in makers:
        pre = simulate_taxed(mkt, sim_start, make(), idx, taxed=False, capital=capital)
        post = simulate_taxed(mkt, sim_start, make(), idx, taxed=True, capital=capital)
        m_pre = lt.metrics(pre["curve"], start, end)
        p0 = next(v for d, v in post["curve"] if d >= start)
        rows.append({"strategy": name, "pre_tax_cagr": m_pre["cagr"], "max_dd": m_pre["max_dd"],
                     # kept_cagr: taxes paid every year, holdings NOT sold at the end
                     "kept_cagr": cagr(p0, post["curve"][-1][1], start, end),
                     # after_tax_cagr: everything sold at the end and that tax paid too ("money in hand")
                     "after_tax_cagr": cagr(p0, post["final_after_tax"], start, end),
                     "final_after_tax": round(post["final_after_tax"]),
                     "tax_paid": round(post["tax_paid"] + post["exit_tax"]), "trades": post["trades"]})
    for r in rows[1:]:
        r["beats_fd_after_tax"] = r["after_tax_cagr"] is not None and r["after_tax_cagr"] > lt.FD_RATE * 100
    return {"version": VERSION, "registered": "2026-10-21", "start": str(start), "end": str(end),
            "years": round(years, 2), "capital": capital, "rows": rows,
            "assumptions": {"income": "total yearly income up to Rs.12 lakh (new regime)", "stcg_pct": STCG * 100,
                            "ltcg_pct": LTCG * 100, "ltcg_exempt": LTCG_EXEMPT, "fd_and_liquid_tax": 0,
                            "rules": "today's rules applied to every year; loss carry-forward without the 8-year limit"},
            "bias_note": "M2 uses today's NIFTY 200 list (optimistic). Information only - confirm tax with a CA."}
