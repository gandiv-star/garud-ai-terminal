"""Point-in-time NIFTY 50 membership (removes survivorship bias from back-tests).

Source: NSE Indices press releases as tabulated on Wikipedia "NIFTY 50" (checked 9 Oct 2026);
the March 2026 review made no NIFTY 50 change.
Rows that share a date in the source table (rowspan) carry that same date here. Each change takes effect ON its date.
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

# (effective date, removed, added) — oldest first
CHANGES = (
    (date(2010, 10, 1), "ABB", "BAJAJ-AUTO"),
    (date(2010, 10, 1), "IDEA", "DRREDDY"),
    (date(2010, 10, 1), "UNITECH", "VEDL"),          # Sesa Goa -> Sesa Sterlite -> Vedanta
    (date(2011, 3, 25), "SUZLON", "GRASIM"),
    (date(2011, 10, 10), "RELCAPITAL", "COALINDIA"),
    (date(2012, 4, 27), "RCOM", "ASIANPAINT"),
    (date(2012, 4, 27), "RPOWER", "BANKBARODA"),
    (date(2012, 9, 28), "SAIL", "LUPIN"),
    (date(2012, 9, 28), "STER", "ULTRACEMCO"),       # Sterlite Industries
    (date(2013, 4, 1), "SIEMENS", "INDUSINDBK"),
    (date(2013, 4, 1), "WIPRO", "NMDC"),
    (date(2013, 9, 27), "RELINFRA", "WIPRO"),
    (date(2014, 3, 28), "JPASSOCIAT", "TECHM"),
    (date(2014, 3, 28), "RANBAXY", "UNITDSPR"),      # United Spirits
    (date(2014, 9, 19), "UNITDSPR", "ZEEL"),
    (date(2015, 3, 27), "DLF", "IDEA"),
    (date(2015, 3, 27), "JINDALSTEL", "YESBANK"),
    (date(2015, 5, 29), "IDFC", "BOSCHLTD"),
    (date(2015, 9, 28), "NMDC", "ADANIPORTS"),
    (date(2016, 4, 1), "CAIRN", "AUROPHARMA"),
    (date(2016, 4, 1), "PNB", "INDUSTOWER"),         # Bharti Infratel
    (date(2016, 4, 1), "VEDL", "EICHERMOT"),
    (date(2017, 3, 31), "BHEL", "SAMMAANCAP"),       # Indiabulls Housing Finance
    (date(2017, 3, 31), "IDEA", "IOC"),
    (date(2017, 5, 26), "GRASIM", "VEDL"),
    (date(2017, 9, 29), "ACC", "BAJFINANCE"),
    (date(2017, 9, 29), "BANKBARODA", "HINDPETRO"),
    (date(2017, 9, 29), "TATAPOWER", "UPL"),
    (date(2018, 4, 2), "AMBUJACEM", "BAJAJFINSV"),
    (date(2018, 4, 2), "AUROPHARMA", "GRASIM"),
    (date(2018, 4, 2), "BOSCHLTD", "TITAN"),
    (date(2018, 9, 28), "LUPIN", "JSWSTEEL"),
    (date(2019, 3, 29), "HINDPETRO", "BRITANNIA"),
    (date(2019, 9, 27), "SAMMAANCAP", "NESTLEIND"),
    (date(2020, 3, 19), "YESBANK", "SHREECEM"),
    (date(2020, 7, 31), "VEDL", "HDFCLIFE"),
    (date(2020, 9, 25), "ZEEL", "SBILIFE"),
    (date(2020, 9, 25), "INDUSTOWER", "DIVISLAB"),
    (date(2021, 3, 31), "GAIL", "TATACONSUM"),
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
ALIASES = {"TMPV": ("TATAMOTORS",), "ETERNAL": ("ZOMATO",), "LTIM": ("LTI",),
           "VEDL": ("SESAGOA", "SSLT"), "INDUSTOWER": ("INFRATEL",), "SAMMAANCAP": ("IBULHSGFIN",),
           "UNITDSPR": ("MCDOWELL-N",), "TATACONSUM": ("TATAGLOBAL",)}


def _initial() -> frozenset:
    s = set(CURRENT)
    for when, removed, added in reversed(CHANGES):
        if added not in s or removed in s:
            raise ValueError(f"inconsistent change list at {when}: -{removed} +{added}")
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
