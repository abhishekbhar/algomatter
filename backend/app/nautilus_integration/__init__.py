"""Nautilus Trader integration for AlgoMatter backtesting."""

from app.nautilus_integration.adapter import NautilusAdapter
from app.nautilus_integration.data import ohlcv_to_bars
from app.nautilus_integration.engine import run_backtest
from app.nautilus_integration.instrument import build_instrument
from app.nautilus_integration.results import extract_results

__all__ = [
    "build_instrument",
    "ohlcv_to_bars",
    "NautilusAdapter",
    "extract_results",
    "run_backtest",
]
