"""Daily reconciliation of LIVE positions against the broker (#26).

Garud checks only the symbols it holds open live positions in (closed ones and the owner's other
holdings are ignored). A protected position (stop placed) must be held at least at the stop
quantity; a BUY still being checked may be held at 0..ordered quantity. Holding LESS than expected is
always a mismatch (stop sold, manual sale, or a missing fill). Holding MORE is reported too — it can
also be the owner's own shares of the same stock, so the message says so. Nothing is bought or sold
automatically by this check.
"""


def expected(entries: dict, gtts: dict, exits: dict) -> dict:
    """{symbol: (min_qty, max_qty)} Garud expects at the broker. entries/gtts/exits: trade_id -> payload
    with 'symbol' (stored by the executor) and 'qty'."""
    out = {}
    for tid, e in entries.items():
        if tid in exits:
            continue
        sym = e.get("symbol")
        if not sym:
            continue
        lo, hi = out.get(sym, (0, 0))
        if tid in gtts:
            q = int(gtts[tid].get("qty") or 0)
            out[sym] = (lo + q, hi + q)
        else:
            out[sym] = (lo, hi + int(e.get("qty") or 0))
    return out


def reconcile(expect: dict, broker_qty: dict) -> list:
    """Mismatches as text. broker_qty: {symbol: qty held at the broker}."""
    problems = []
    for sym in sorted(expect):
        lo, hi = expect[sym]
        held = int(broker_qty.get(sym, 0))
        want = f"{lo}" if lo == hi else f"{lo}–{hi}"
        if held < lo:
            problems.append(f"{sym}: broker holds {held}, Garud expects {want} — shares missing")
        elif held > hi:
            problems.append(f"{sym}: broker holds {held}, Garud expects {want} — extra shares "
                            "(your own holding of the same stock?)")
    return problems


def broker_quantities(broker) -> dict:
    """{symbol: largest qty in positions or holdings}. Raises if the broker cannot be read."""
    out = {}
    for fetch in (broker.get_positions, broker.get_holdings):
        body = fetch()
        rows = body.get("data") if isinstance(body, dict) else body
        for row in rows or []:
            sym = row.get("tradingsymbol") or row.get("trading_symbol")
            if sym:
                out[sym] = max(out.get(sym, 0), int(row.get("quantity") or 0))
    return out
