"""Point-in-time NIFTY 50 membership (removes survivorship bias from back-tests).

Source: NSE Indices press releases as tabulated on Wikipedia "NIFTY 50" (checked 9 Oct 2026);
the March 2026 review made no NIFTY 50 change. Each change takes effect ON its date.
Tata Motors continues as TMPV (passenger vehicles) after the Oct 2025 demerger.
"""
from datetime import date

CURRENT = (
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE",
    "BAJAJFINSV", "BEL", "BHARTIARTL", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDIGO",
    "INFY", "ITC", "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT", "M&M", "MARUTI", "MAXHEALTH",
    "NESTLEIND", "NTPC", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN",
    "SUNPHARMA", "TCS", "TATACONSUM", "TMPV", "TATASTEEL", "TECHM", "TITAN", "TRENT",
    "ULTRACEMCO", "WIPRO",
)

# (effective date, removed, added)
CHANGES = (
    (date(2022, 3, 31), "IOC", "APOLLOHOSP"),
    (date(2022, 9, 30), "SHREECEM", "ADANIENT"),
    (date(2023, 7, 13), "HDFC", "LTIM"),
    (date(2024, 3, 28), "UPL", "SHRIRAMFIN"),
    (date(2024, 9, 30), "DIVISLAB", "BEL"),
    (date(2024, 9, 30), "LTIM", "TRENT"),
    (date(2025, 3, 28), "BPCL", "JIOFIN"),
    (date(2025, 3, 28), "BRITANNIA", "ETERNAL"),
    (date(2025, 9, 30), "HEROMOTOCO", "INDIGO"),
    (date(2025, 9, 30), "INDUSINDBK", "MAXHEALTH"),
)

# renamed tickers: older history may only exist under the old symbol
ALIASES = {"TMPV": ("TATAMOTORS",), "ETERNAL": ("ZOMATO",), "LTIM": ("LTI",)}


def _initial() -> frozenset:
    s = set(CURRENT)
    for _, removed, added in reversed(CHANGES):
        s.discard(added)
        s.add(removed)
    return frozenset(s)


INITIAL = _initial()   # membership before the first listed change


def members_on(d: date) -> frozenset:
    s = set(INITIAL)
    for when, removed, added in CHANGES:
        if when <= d:
            s.discard(removed)
            s.add(added)
    return frozenset(s)


def all_symbols() -> tuple:
    return tuple(sorted(set(CURRENT) | {r for _, r, _ in CHANGES} | {a for _, _, a in CHANGES}))


def stitch(primary: dict, alias: dict) -> dict:
    """Fill dates before the primary series starts from the alias series, scaled so the two join
    without a jump (a rename or demerger is not a gain or loss for the holder)."""
    if not alias:
        return dict(primary)
    if not primary:
        return dict(alias)
    first = min(primary)
    before = [d for d in alias if d <= first]
    if not before:
        return dict(primary)
    ratio = primary[first] / alias[max(before)]
    out = {d: p * ratio for d, p in alias.items() if d < first}
    out.update(primary)
    return out
