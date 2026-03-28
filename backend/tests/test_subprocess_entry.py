import json
import pytest
from app.strategy_sdk.subprocess_entry import run_tick, run_from_stdin_payload
from app.strategy_sdk.sandbox import SafeImporter


class TestSafeImporter:
    def test_allows_math(self):
        importer = SafeImporter()
        mod = importer("math")
        assert hasattr(mod, "sqrt")

    def test_allows_datetime(self):
        importer = SafeImporter()
        mod = importer("datetime")
        assert hasattr(mod, "datetime")

    def test_blocks_os(self):
        importer = SafeImporter()
        with pytest.raises(ImportError, match="not allowed"):
            importer("os")

    def test_blocks_subprocess(self):
        importer = SafeImporter()
        with pytest.raises(ImportError, match="not allowed"):
            importer("subprocess")

    def test_blocks_socket(self):
        importer = SafeImporter()
        with pytest.raises(ImportError, match="not allowed"):
            importer("socket")


class TestRunTick:
    def test_basic_strategy_execution(self):
        code = '''
class Strategy(AlgoMatterStrategy):
    def on_init(self):
        self.state.setdefault("count", 0)

    def on_candle(self, candle):
        self.state["count"] += 1
        if candle.close > 100:
            self.buy(quantity=1)
        self.log(f"Processed candle {self.state['count']}")
'''
        payload = {
            "code": code,
            "entrypoint": "Strategy",
            "candle": {"timestamp": "2026-01-01T00:00:00Z", "open": 105, "high": 106, "low": 104, "close": 105, "volume": 1000},
            "history": [],
            "state": {"position": None, "open_orders": [], "portfolio": {"balance": 10000, "equity": 10000, "available_margin": 10000}, "user_state": {}},
            "order_updates": [],
            "params": {},
            "mode": "paper",
        }
        result = run_tick(payload)
        assert result["error"] is None
        assert len(result["orders"]) == 1
        assert result["orders"][0]["action"] == "buy"
        assert result["state"]["user_state"]["count"] == 1
        assert len(result["logs"]) == 1

    def test_syntax_error_in_code(self):
        payload = {
            "code": "class Strategy(AlgoMatterStrategy):\n    def on_candle(self, candle)\n        pass",
            "entrypoint": "Strategy",
            "candle": {"timestamp": "2026-01-01T00:00:00Z", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            "history": [],
            "state": {"position": None, "open_orders": [], "portfolio": {"balance": 10000, "equity": 10000, "available_margin": 10000}, "user_state": {}},
            "order_updates": [],
            "params": {},
            "mode": "paper",
        }
        result = run_tick(payload)
        assert result["error"] is not None
        assert result["error"]["type"] == "syntax"

    def test_runtime_error_in_code(self):
        code = '''
class Strategy(AlgoMatterStrategy):
    def on_candle(self, candle):
        x = 1 / 0
'''
        payload = {
            "code": code,
            "entrypoint": "Strategy",
            "candle": {"timestamp": "2026-01-01T00:00:00Z", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            "history": [],
            "state": {"position": None, "open_orders": [], "portfolio": {"balance": 10000, "equity": 10000, "available_margin": 10000}, "user_state": {}},
            "order_updates": [],
            "params": {},
            "mode": "paper",
        }
        result = run_tick(payload)
        assert result["error"] is not None
        assert result["error"]["type"] == "runtime"
        assert "ZeroDivisionError" in result["error"]["message"]

    def test_order_updates_trigger_callback(self):
        code = '''
class Strategy(AlgoMatterStrategy):
    def on_order_update(self, order_id, status, fill_price, fill_quantity):
        self.log(f"Order {order_id} was {status}")

    def on_candle(self, candle):
        pass
'''
        payload = {
            "code": code,
            "entrypoint": "Strategy",
            "candle": {"timestamp": "2026-01-01T00:00:00Z", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            "history": [],
            "state": {"position": None, "open_orders": [], "portfolio": {"balance": 10000, "equity": 10000, "available_margin": 10000}, "user_state": {}},
            "order_updates": [{"order_id": "abc-123", "status": "filled", "fill_price": 100.5, "fill_quantity": 1}],
            "params": {},
            "mode": "paper",
        }
        result = run_tick(payload)
        assert result["error"] is None
        assert len(result["logs"]) == 1
        assert "filled" in result["logs"][0]["message"]
