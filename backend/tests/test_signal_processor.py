import pytest
from decimal import Decimal
from app.webhooks.processor import evaluate_rules, RuleResult
from app.webhooks.schemas import StandardSignal


def make_signal(**overrides) -> StandardSignal:
    defaults = dict(
        symbol="RELIANCE",
        exchange="NSE",
        action="BUY",
        quantity=Decimal("10"),
        order_type="MARKET",
        product_type="INTRADAY",
    )
    defaults.update(overrides)
    return StandardSignal(**defaults)


def test_no_rules_passes():
    result = evaluate_rules(make_signal(), {}, open_positions=0, signals_today=0)
    assert result.passed is True


def test_symbol_whitelist_pass():
    rules = {"symbol_whitelist": ["RELIANCE", "TCS"]}
    result = evaluate_rules(make_signal(symbol="RELIANCE"), rules, 0, 0)
    assert result.passed is True


def test_symbol_whitelist_block():
    rules = {"symbol_whitelist": ["TCS", "INFY"]}
    result = evaluate_rules(make_signal(symbol="RELIANCE"), rules, 0, 0)
    assert result.passed is False
    assert "whitelist" in result.reason


def test_symbol_blacklist_block():
    rules = {"symbol_blacklist": ["RELIANCE"]}
    result = evaluate_rules(make_signal(symbol="RELIANCE"), rules, 0, 0)
    assert result.passed is False


def test_max_open_positions_block():
    rules = {"max_open_positions": 5}
    result = evaluate_rules(make_signal(), rules, open_positions=5, signals_today=0)
    assert result.passed is False


def test_max_position_size_block():
    rules = {"max_position_size": 100}
    signal = make_signal(quantity=Decimal("200"))
    result = evaluate_rules(signal, rules, 0, 0)
    assert result.passed is False


def test_max_signals_per_day_block():
    rules = {"max_signals_per_day": 10}
    result = evaluate_rules(make_signal(), rules, 0, signals_today=10)
    assert result.passed is False


def test_trading_hours_block():
    rules = {
        "trading_hours": {
            "start": "09:15",
            "end": "15:30",
            "timezone": "Asia/Kolkata",
        }
    }
    result = evaluate_rules(
        make_signal(),
        rules,
        0,
        0,
        current_time_str="03:00",  # 3 AM IST — outside hours
    )
    assert result.passed is False
