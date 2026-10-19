"""pytest setup: repository root on the import path, real libraries when installed (CI),
small stand-ins only when they are missing (offline local runs), network blocked, and every
live-trading variable cleared before and after each test."""
import os
import sys

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
for p in (ROOT, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)
try:
    import yfinance  # noqa: F401
except ImportError:
    # Offline local runs only (CI installs the real package): a stand-in that refuses to download.
    import types

    def _no_download(*args, **kwargs):
        raise RuntimeError("tests must not download market data (yfinance stand-in)")

    _yf = types.ModuleType("yfinance")
    _yf.Ticker = type("Ticker", (), {"__init__": lambda self, symbol: None, "history": _no_download})
    _yf.download = _no_download
    sys.modules["yfinance"] = _yf

import helpers  # noqa: E402
import pytest  # noqa: E402

helpers.block_network()


@pytest.fixture(autouse=True)
def _clean_live_env():
    helpers.clean_env()
    yield
    helpers.clean_env()
