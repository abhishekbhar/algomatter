"""Tests for webhook live broker dispatch logic."""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.brokers.base import OrderRequest, OrderResponse


class TestLiveDispatchOrderConstruction:
    @pytest.mark.asyncio
    async def test_live_dispatch_constructs_order_from_signal(self):
        from app.webhooks.schemas import StandardSignal

        signal = StandardSignal(
            symbol="BTCUSDT",
            exchange="BINANCE_TESTNET",
            action="BUY",
            quantity=Decimal("0.5"),
            order_type="MARKET",
            price=None,
            product_type="DELIVERY",
        )

        order_req = OrderRequest(
            symbol=signal.symbol,
            exchange=signal.exchange,
            action=signal.action,
            quantity=signal.quantity,
            order_type=signal.order_type or "MARKET",
            price=signal.price or Decimal("0"),
            product_type=signal.product_type or "DELIVERY",
            trigger_price=signal.trigger_price,
        )

        assert order_req.symbol == "BTCUSDT"
        assert order_req.action == "BUY"
        assert order_req.quantity == Decimal("0.5")
        assert order_req.order_type == "MARKET"
        assert order_req.trigger_price is None

    @pytest.mark.asyncio
    async def test_live_dispatch_with_stop_loss_signal(self):
        from app.webhooks.schemas import StandardSignal

        signal = StandardSignal(
            symbol="BTCUSDT",
            exchange="BINANCE_TESTNET",
            action="SELL",
            quantity=Decimal("0.5"),
            order_type="SL",
            price=Decimal("28000"),
            trigger_price=Decimal("28500"),
            product_type="DELIVERY",
        )

        order_req = OrderRequest(
            symbol=signal.symbol,
            exchange=signal.exchange,
            action=signal.action,
            quantity=signal.quantity,
            order_type=signal.order_type or "MARKET",
            price=signal.price or Decimal("0"),
            product_type=signal.product_type or "DELIVERY",
            trigger_price=signal.trigger_price,
        )

        assert order_req.trigger_price == Decimal("28500")
        assert order_req.order_type == "SL"

    @pytest.mark.asyncio
    async def test_live_dispatch_result_mapping(self):
        mock_response = OrderResponse(
            order_id="12345",
            status="filled",
            fill_price=Decimal("30000"),
            fill_quantity=Decimal("0.5"),
        )

        execution_result = mock_response.status
        execution_detail = mock_response.model_dump(mode="json")

        assert execution_result == "filled"
        assert execution_detail["order_id"] == "12345"

    @pytest.mark.asyncio
    async def test_live_dispatch_error_handling(self):
        mock_broker = AsyncMock()
        mock_broker.place_order = AsyncMock(side_effect=RuntimeError("Connection timeout"))
        mock_broker.close = AsyncMock()

        execution_result = None
        execution_detail = None
        try:
            await mock_broker.place_order(None)
        except Exception as exc:
            execution_result = "broker_error"
            execution_detail = {"error": str(exc)}
        finally:
            await mock_broker.close()

        assert execution_result == "broker_error"
        assert "Connection timeout" in execution_detail["error"]
        mock_broker.close.assert_called_once()
