import pytest
from app.webhooks.mapper import apply_mapping
from app.webhooks.schemas import StandardSignal

def test_mapping_with_jsonpath():
    payload = {
        "ticker": "RELIANCE",
        "exchange": "NSE",
        "strategy": {"order_action": "buy", "order_contracts": "10"}
    }
    template = {
        "symbol": "$.ticker",
        "exchange": "$.exchange",
        "action": "$.strategy.order_action",
        "quantity": "$.strategy.order_contracts",
        "order_type": "MARKET",
        "product_type": "INTRADAY",
    }
    signal = apply_mapping(payload, template)
    assert isinstance(signal, StandardSignal)
    assert signal.symbol == "RELIANCE"
    assert signal.action == "BUY"  # normalized to uppercase
    assert signal.quantity == 10
    assert signal.order_type == "MARKET"

def test_mapping_with_literal_values():
    payload = {"sym": "TCS"}
    template = {
        "symbol": "$.sym",
        "exchange": "NSE",
        "action": "BUY",
        "quantity": "5",
        "order_type": "MARKET",
        "product_type": "INTRADAY",
    }
    signal = apply_mapping(payload, template)
    assert signal.symbol == "TCS"
    assert signal.exchange == "NSE"

def test_mapping_missing_jsonpath_raises():
    payload = {"foo": "bar"}
    template = {"symbol": "$.nonexistent", "exchange": "NSE", "action": "BUY",
                "quantity": "1", "order_type": "MARKET", "product_type": "INTRADAY"}
    with pytest.raises(ValueError, match="Failed to resolve"):
        apply_mapping(payload, template)

def test_mapping_tradingview_format():
    """Real TradingView webhook payload."""
    payload = {
        "ticker": "NIFTY",
        "exchange": "NSE",
        "close": 22500.50,
        "strategy": {
            "order_action": "sell",
            "order_contracts": "50",
            "order_price": "22500.50",
            "order_id": "Long Entry"
        }
    }
    template = {
        "symbol": "$.ticker",
        "exchange": "$.exchange",
        "action": "$.strategy.order_action",
        "quantity": "$.strategy.order_contracts",
        "order_type": "MARKET",
        "price": "$.strategy.order_price",
        "product_type": "INTRADAY",
    }
    signal = apply_mapping(payload, template)
    assert signal.symbol == "NIFTY"
    assert signal.action == "SELL"
    assert signal.quantity == 50
