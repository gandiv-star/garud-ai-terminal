from datetime import datetime

import yfinance as yf

from data.data_loader import Bar, DataLoader


def to_yfinance_symbol(nse_symbol: str) -> str:
    if nse_symbol.endswith(".NS"):
        return nse_symbol
    return f"{nse_symbol}.NS"


class YFinanceLoader(DataLoader):
    def get_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[Bar]:
        ticker = yf.Ticker(to_yfinance_symbol(symbol))
        df = ticker.history(start=start, end=end, interval=interval)
        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])

        bars: list[Bar] = []
        for timestamp, row in df.iterrows():
            bars.append(
                Bar(
                    symbol=symbol,
                    timestamp=timestamp.to_pydatetime(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                )
            )
        return bars

    def get_latest_quote(self, symbol: str) -> Bar:
        raise NotImplementedError(
            "YFinanceLoader is for historical/backtesting data only. "
            "Use UpstoxLoader for live quotes."
        )

    def get_universe(self) -> list[str]:
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]

    def get_corporate_actions(self, symbol: str, start: datetime, end: datetime) -> list[dict]:
        ticker = yf.Ticker(to_yfinance_symbol(symbol))
        actions = ticker.actions
        events: list[dict] = []
        start_date, end_date = start.date(), end.date()
        for timestamp, row in actions.iterrows():
            # Compare dates only — yfinance's action timestamps are
            # timezone-aware and start/end here may not be, so comparing
            # full datetimes can raise "can't compare offset-naive and
            # offset-aware datetimes". Corporate action dates don't need
            # intraday precision anyway.
            if start_date <= timestamp.date() <= end_date:
                if row.get("Dividends", 0):
                    events.append({"type": "dividend", "date": timestamp, "value": float(row["Dividends"])})
                if row.get("Stock Splits", 0):
                    events.append({"type": "split", "date": timestamp, "value": float(row["Stock Splits"])})
        return events
