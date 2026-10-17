"""Advanced chart for the Garud app (daily bars only — no intraday data is implied).
Indicators are computed here in plain Python so they are testable; Plotly only draws."""
from datetime import date

UP, DOWN, BLUE, AMBER, MUTED, GRID = "#22C55E", "#EF4444", "#4C8DFF", "#F59E0B", "#94A3B8", "#1A2F4D"


def sma(xs: list, n: int) -> list:
    out, s = [], 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        out.append(s / n if i >= n - 1 else None)
    return out


def ema(xs: list, n: int) -> list:
    out, k, e = [], 2 / (n + 1), None
    for i, x in enumerate(xs):
        if i < n - 1:
            out.append(None)
            continue
        e = sum(xs[i - n + 1:i + 1]) / n if e is None else x * k + e * (1 - k)
        out.append(e)
    return out


def rsi(xs: list, n: int = 14) -> list:
    """Wilder's RSI."""
    out = [None] * len(xs)
    if len(xs) <= n:
        return out
    gains = [max(xs[i] - xs[i - 1], 0) for i in range(1, len(xs))]
    losses = [max(xs[i - 1] - xs[i], 0) for i in range(1, len(xs))]
    ag, al = sum(gains[:n]) / n, sum(losses[:n]) / n
    for i in range(n, len(xs)):
        if i > n:
            ag = (ag * (n - 1) + gains[i - 1]) / n
            al = (al * (n - 1) + losses[i - 1]) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def macd(xs: list, fast: int = 12, slow: int = 26, signal: int = 9):
    ef, es = ema(xs, fast), ema(xs, slow)
    line = [a - b if a is not None and b is not None else None for a, b in zip(ef, es)]
    valid = [v for v in line if v is not None]
    sig_valid = ema(valid, signal) if len(valid) >= signal else [None] * len(valid)
    sig = [None] * (len(line) - len(valid)) + sig_valid
    hist = [a - b if a is not None and b is not None else None for a, b in zip(line, sig)]
    return line, sig, hist


def series(bars: list) -> dict:
    closes = [b.close for b in bars]
    line, sig, hist = macd(closes)
    return {"dates": [b.timestamp for b in bars], "open": [b.open for b in bars], "high": [b.high for b in bars],
            "low": [b.low for b in bars], "close": closes, "volume": [b.volume for b in bars],
            "sma20": sma(closes, 20), "sma50": sma(closes, 50), "sma200": sma(closes, 200),
            "rsi": rsi(closes), "macd": line, "signal": sig, "hist": hist}


def build_figure(s: dict, show_from: int, markers: list, levels: list, title: str):
    """s: series(); show_from: index of first bar to display (indicators use the full history);
    markers: [(date, price, 'entry'|'exit', label)]; levels: [(price, label, color)]."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    sl = slice(show_from, None)
    x = s["dates"][sl]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                        row_heights=[0.55, 0.13, 0.16, 0.16])
    fig.add_trace(go.Candlestick(x=x, open=s["open"][sl], high=s["high"][sl], low=s["low"][sl],
                                 close=s["close"][sl], name="Price", increasing_line_color=UP,
                                 decreasing_line_color=DOWN, showlegend=False), row=1, col=1)
    for key, col, name in (("sma20", AMBER, "SMA20"), ("sma50", BLUE, "SMA50"), ("sma200", MUTED, "SMA200")):
        fig.add_trace(go.Scatter(x=x, y=s[key][sl], name=name, line=dict(color=col, width=1.2)), row=1, col=1)
    for kind, sym, col in (("entry", "triangle-up", UP), ("exit", "triangle-down", DOWN)):
        pts = [m for m in markers if m[2] == kind]
        if pts:
            fig.add_trace(go.Scatter(x=[m[0] for m in pts], y=[m[1] for m in pts], mode="markers",
                                     marker=dict(symbol=sym, size=11, color=col, line=dict(width=1, color="white")),
                                     text=[m[3] for m in pts], hoverinfo="text",
                                     name="Paper entry" if kind == "entry" else "Paper exit"), row=1, col=1)
    for price, label, col in levels:
        fig.add_hline(y=price, line=dict(color=col, dash="dash", width=1), annotation_text=label,
                      annotation_position="top left", row=1, col=1)
    vcol = [UP if c >= o else DOWN for o, c in zip(s["open"][sl], s["close"][sl])]
    fig.add_trace(go.Bar(x=x, y=s["volume"][sl], marker_color=vcol, name="Volume", showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=s["rsi"][sl], name="RSI14", line=dict(color=BLUE, width=1.2),
                             showlegend=False), row=3, col=1)
    for lvl in (30, 70):
        fig.add_hline(y=lvl, line=dict(color=MUTED, dash="dot", width=1), row=3, col=1)
    fig.add_trace(go.Bar(x=x, y=s["hist"][sl], marker_color=[UP if (h or 0) >= 0 else DOWN for h in s["hist"][sl]],
                         name="MACD hist", showlegend=False), row=4, col=1)
    fig.add_trace(go.Scatter(x=x, y=s["macd"][sl], name="MACD", line=dict(color=BLUE, width=1),
                             showlegend=False), row=4, col=1)
    fig.add_trace(go.Scatter(x=x, y=s["signal"][sl], name="Signal", line=dict(color=AMBER, width=1),
                             showlegend=False), row=4, col=1)
    fig.update_layout(height=760, margin=dict(l=8, r=8, t=36, b=8), title=dict(text=title, x=0.01),
                      paper_bgcolor="#0A1628", plot_bgcolor="#0A1628", font=dict(color="#E6EDF7", size=11),
                      legend=dict(orientation="h", y=1.02, x=0, font=dict(size=10)),
                      xaxis_rangeslider_visible=False, hovermode="x unified")
    fig.update_xaxes(gridcolor=GRID, rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_yaxes(gridcolor=GRID)
    for r, t in ((2, "Vol"), (3, "RSI"), (4, "MACD")):
        fig.update_yaxes(title_text=t, row=r, col=1)
    fig.update_yaxes(range=[0, 100], tickvals=[30, 50, 70], row=3, col=1)   # RSI always 0-100
    fig.update_layout(dragmode=False)                                       # no accidental pan/zoom on phones
    return fig


def start_index(dates: list, start: date) -> int:
    for i, d in enumerate(dates):
        if (d.date() if hasattr(d, "date") else d) >= start:
            return i
    return max(len(dates) - 1, 0)
