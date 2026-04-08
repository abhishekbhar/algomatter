import pytest

from app.config import Settings


def test_settings_default_paper_trading_enabled():
    s = Settings()
    assert s.enable_paper_trading is True


def test_settings_default_backtesting_enabled():
    s = Settings()
    assert s.enable_backtesting is True


def test_settings_reads_paper_trading_env(monkeypatch):
    monkeypatch.setenv("ALGOMATTER_ENABLE_PAPER_TRADING", "false")
    s = Settings()
    assert s.enable_paper_trading is False


def test_settings_reads_backtesting_env(monkeypatch):
    monkeypatch.setenv("ALGOMATTER_ENABLE_BACKTESTING", "false")
    s = Settings()
    assert s.enable_backtesting is False
