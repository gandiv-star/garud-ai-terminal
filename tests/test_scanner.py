"""Smart scanner snapshot (scan_v1) with fake market data — no download."""
import random
from datetime import date, datetime

from helpers import IST, bar, trading_days

from backtest import paper_rule, scanner
from strategies.registry import STRATEGY_REGISTRY

DAYS = trading_days(date(2025, 8, 1), 260)


class Data:
    def __init__(self, broken=("DLF",)):
        self.now = datetime.combine(DAYS[-1], datetime.min.time()).replace(hour=18, tzinfo=IST)
        self.broken = set(broken)

    def nifty_completed(self):
        return [(d, 25000 * 0.999 ** i) for i, d in enumerate(DAYS)]

    def bars(self, sym):
        if sym in self.broken:
            raise RuntimeError("no data")
        rnd, p, out = random.Random(sym), 1000.0, []
        for d in DAYS:
            o = p
            p *= 1 + rnd.gauss(0, 0.015)
            out.append(bar(d, o, max(o, p) * 1.005, min(o, p) * 0.995, p, sym, 100000 + rnd.randint(0, 50000)))
        return out


def test_snapshot_every_stock_once_and_valid_actions():
    rules = (paper_rule.RULE_V1,)
    snap = scanner.build_snapshot(Data(), STRATEGY_REGISTRY, [], rules=rules)
    syms = [r["symbol"] for r in snap["rows"]]
    assert sorted(syms) == sorted(paper_rule.UNIVERSE_8) and len(set(syms)) == len(syms)
    assert {r["action"] for r in snap["rows"]} <= set(scanner.ORDER)
    assert [r for r in snap["rows"] if r["symbol"] == "DLF"][0]["action"] == "DATA ISSUE"
    assert snap["version"] == "scan_v1" and snap["regime"] == "WEAK_BEAR"
    assert sum(snap["counts"].values()) == len(syms)
    for r in snap["rows"]:
        if r["action"] == "BUY CANDIDATE":
            assert r["ref"] and r["ref"]["qty"] > 0 and r["ref"]["stop"] < r["ref"]["close"]
