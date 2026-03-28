"""Tests for the strategy-runner service components."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.strategy_runner.executor import run_subprocess
from app.strategy_runner.order_router import translate_order, ORDER_TYPE_MAP
from app.strategy_runner.health import FailureTracker


# ---------------------------------------------------------------------------
# executor.run_subprocess tests
# ---------------------------------------------------------------------------

class TestRunSubprocess:
    """Test executor.run_subprocess with mocked subprocess."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Mock subprocess returns valid JSON; verify round-trip."""
        expected = {
            "orders": [{"id": "o1", "action": "buy", "quantity": 10}],
            "cancelled_orders": [],
            "state": {"user_state": {"counter": 1}},
            "logs": [{"level": "info", "message": "tick ok"}],
            "error": None,
        }

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(json.dumps(expected).encode(), b"")
        )
        mock_process.returncode = 0

        with patch("app.strategy_runner.executor.asyncio.create_subprocess_exec", return_value=mock_process):
            result = await run_subprocess({"code": "pass", "state": {"user_state": {}}})

        assert result["orders"] == expected["orders"]
        assert result["state"]["user_state"]["counter"] == 1
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_nonzero_exit_code(self):
        """When subprocess returns non-zero, result should contain a runtime error."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"some error"))
        mock_process.returncode = 1

        with patch("app.strategy_runner.executor.asyncio.create_subprocess_exec", return_value=mock_process):
            result = await run_subprocess({"code": "bad", "state": {"user_state": {"x": 1}}})

        assert result["error"] is not None
        assert result["error"]["type"] == "runtime"
        assert "exited with code 1" in result["error"]["message"]
        # User state should be preserved
        assert result["state"]["user_state"]["x"] == 1

    @pytest.mark.asyncio
    async def test_timeout(self):
        """When subprocess exceeds timeout, result should contain a timeout error."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_process.kill = MagicMock()

        with patch("app.strategy_runner.executor.asyncio.create_subprocess_exec", return_value=mock_process):
            # Patch wait_for to raise immediately
            with patch("app.strategy_runner.executor.asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                result = await run_subprocess({"code": "slow", "state": {"user_state": {}}}, timeout=1)

        assert result["error"]["type"] == "timeout"
        mock_process.kill.assert_called_once()


# ---------------------------------------------------------------------------
# order_router.translate_order tests
# ---------------------------------------------------------------------------

class TestTranslateOrder:
    """Test order_router.translate_order type mapping and exchange filtering."""

    def _make_deployment(self, exchange="binance_testnet", mode="paper", symbol="BTCUSDT", product_type="DELIVERY"):
        dep = MagicMock()
        dep.exchange = exchange
        dep.mode = mode
        dep.symbol = symbol
        dep.product_type = product_type
        return dep

    def test_market_order_mapping(self):
        deployment = self._make_deployment()
        order = {"action": "buy", "quantity": 5, "order_type": "market"}
        result = translate_order(order, deployment)
        assert result is not None
        assert result["order_type"] == "MARKET"
        assert result["action"] == "BUY"
        assert result["quantity"] == 5
        assert result["symbol"] == "BTCUSDT"

    def test_limit_order_mapping(self):
        deployment = self._make_deployment()
        order = {"action": "sell", "quantity": 3, "order_type": "limit", "price": 100.0}
        result = translate_order(order, deployment)
        assert result is not None
        assert result["order_type"] == "LIMIT"
        assert result["price"] == 100.0

    def test_stop_order_mapping(self):
        """Stop orders should map to SL-M on non-Exchange1 brokers."""
        deployment = self._make_deployment(exchange="binance_testnet")
        order = {"action": "sell", "quantity": 2, "order_type": "stop", "trigger_price": 95.0}
        result = translate_order(order, deployment)
        assert result is not None
        assert result["order_type"] == "SL-M"

    def test_stop_limit_order_mapping(self):
        deployment = self._make_deployment(exchange="binance_testnet")
        order = {"action": "buy", "quantity": 1, "order_type": "stop_limit", "price": 105.0, "trigger_price": 100.0}
        result = translate_order(order, deployment)
        assert result is not None
        assert result["order_type"] == "SL"

    def test_default_order_type(self):
        """When order_type is missing, it should default to MARKET."""
        deployment = self._make_deployment()
        order = {"action": "buy", "quantity": 1}
        result = translate_order(order, deployment)
        assert result is not None
        assert result["order_type"] == "MARKET"

    def test_exchange1_rejects_stop_orders(self):
        """Exchange1 does not support stop orders; translate_order should return None."""
        deployment = self._make_deployment(exchange="exchange1")
        order = {"action": "sell", "quantity": 2, "order_type": "stop", "trigger_price": 95.0}
        result = translate_order(order, deployment)
        assert result is None

    def test_exchange1_rejects_stop_limit_orders(self):
        """Exchange1 does not support stop_limit orders; translate_order should return None."""
        deployment = self._make_deployment(exchange="exchange1")
        order = {"action": "buy", "quantity": 1, "order_type": "stop_limit", "price": 105.0, "trigger_price": 100.0}
        result = translate_order(order, deployment)
        assert result is None

    def test_exchange1_accepts_market_orders(self):
        """Exchange1 should accept market orders."""
        deployment = self._make_deployment(exchange="exchange1")
        order = {"action": "buy", "quantity": 10, "order_type": "market"}
        result = translate_order(order, deployment)
        assert result is not None
        assert result["order_type"] == "MARKET"

    def test_exchange1_accepts_limit_orders(self):
        """Exchange1 should accept limit orders."""
        deployment = self._make_deployment(exchange="exchange1")
        order = {"action": "sell", "quantity": 5, "order_type": "limit", "price": 50.0}
        result = translate_order(order, deployment)
        assert result is not None
        assert result["order_type"] == "LIMIT"


# ---------------------------------------------------------------------------
# health.FailureTracker tests
# ---------------------------------------------------------------------------

class TestFailureTracker:
    """Test the FailureTracker auto-pause behavior."""

    def test_auto_pause_after_threshold(self):
        """Deployment should be auto-paused after reaching failure threshold."""
        tracker = FailureTracker(threshold=3)
        dep_id = "dep-001"

        assert not tracker.record_failure(dep_id)  # 1st failure
        assert not tracker.is_paused(dep_id)

        assert not tracker.record_failure(dep_id)  # 2nd failure
        assert not tracker.is_paused(dep_id)

        assert tracker.record_failure(dep_id)       # 3rd failure -> auto-pause
        assert tracker.is_paused(dep_id)

    def test_reset_on_success(self):
        """Failure counter should reset to zero after a success."""
        tracker = FailureTracker(threshold=3)
        dep_id = "dep-002"

        tracker.record_failure(dep_id)  # 1
        tracker.record_failure(dep_id)  # 2
        tracker.record_success(dep_id)  # reset

        # After reset, it should take 3 more failures to pause
        assert not tracker.record_failure(dep_id)  # 1
        assert not tracker.record_failure(dep_id)  # 2
        assert not tracker.is_paused(dep_id)
        assert tracker.record_failure(dep_id)       # 3 -> paused
        assert tracker.is_paused(dep_id)

    def test_manual_reset(self):
        """Manual reset should clear both failure count and paused state."""
        tracker = FailureTracker(threshold=2)
        dep_id = "dep-003"

        tracker.record_failure(dep_id)
        tracker.record_failure(dep_id)
        assert tracker.is_paused(dep_id)

        tracker.reset(dep_id)
        assert not tracker.is_paused(dep_id)
        assert dep_id not in tracker._failures

    def test_status_property(self):
        """Status should report tracked deployments and paused list."""
        tracker = FailureTracker(threshold=2)
        tracker.record_failure("a")
        tracker.record_failure("b")
        tracker.record_failure("b")  # pauses b

        status = tracker.status
        assert status["tracked"] == 2
        assert "b" in status["paused"]
        assert "a" not in status["paused"]

    def test_threshold_one(self):
        """With threshold=1, first failure should trigger auto-pause."""
        tracker = FailureTracker(threshold=1)
        assert tracker.record_failure("dep-x")
        assert tracker.is_paused("dep-x")
