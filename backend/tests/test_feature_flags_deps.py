import pytest
from fastapi import HTTPException

from app.config import settings
from app.feature_flags import (
    require_backtesting_enabled,
    require_paper_trading_enabled,
)


def test_require_paper_trading_enabled_noop_when_on(monkeypatch):
    monkeypatch.setattr(settings, "enable_paper_trading", True)
    # Should not raise
    require_paper_trading_enabled()


def test_require_paper_trading_enabled_raises_when_off(monkeypatch):
    monkeypatch.setattr(settings, "enable_paper_trading", False)
    with pytest.raises(HTTPException) as exc:
        require_paper_trading_enabled()
    assert exc.value.status_code == 403
    assert "paper trading" in exc.value.detail.lower()


def test_require_backtesting_enabled_noop_when_on(monkeypatch):
    monkeypatch.setattr(settings, "enable_backtesting", True)
    require_backtesting_enabled()


def test_require_backtesting_enabled_raises_when_off(monkeypatch):
    monkeypatch.setattr(settings, "enable_backtesting", False)
    with pytest.raises(HTTPException) as exc:
        require_backtesting_enabled()
    assert exc.value.status_code == 403
    assert "backtesting" in exc.value.detail.lower()
