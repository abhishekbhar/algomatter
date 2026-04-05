import ast
import json
import sys
import traceback
import types
from datetime import datetime, timezone

from app.strategy_sdk.base import AlgoMatterStrategy
from app.strategy_sdk.models import Candle, Position, Portfolio, PendingOrder


def _parse_candle(data: dict) -> Candle:
    ts = data["timestamp"]
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return Candle(
        symbol=data["symbol"],
        timestamp=ts,
        open=float(data["open"]),
        high=float(data["high"]),
        low=float(data["low"]),
        close=float(data["close"]),
        volume=float(data["volume"]),
    )


def _restore_state(state: dict) -> tuple[Position | None, list[PendingOrder], Portfolio, dict]:
    position = None
    if state.get("position"):
        p = state["position"]
        position = Position(
            quantity=float(p["quantity"]),
            avg_entry_price=float(p["avg_entry_price"]),
            unrealized_pnl=float(p.get("unrealized_pnl", 0)),
        )

    open_orders = []
    for o in state.get("open_orders", []):
        open_orders.append(PendingOrder(
            id=o["id"], action=o["action"], quantity=float(o["quantity"]),
            order_type=o["order_type"], price=o.get("price"),
            trigger_price=o.get("trigger_price"), age_candles=o.get("age_candles", 0),
        ))

    pf = state.get("portfolio", {})
    portfolio = Portfolio(
        balance=float(pf.get("balance", 0)),
        equity=float(pf.get("equity", 0)),
        available_margin=float(pf.get("available_margin", 0)),
    )

    user_state = state.get("user_state", {})
    return position, open_orders, portfolio, user_state


def run_tick(payload: dict) -> dict:
    code = payload["code"]
    entrypoint = payload.get("entrypoint", "Strategy")

    # Parse code -- catch syntax errors
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {
            "orders": [], "cancelled_orders": [], "state": {"user_state": {}},
            "logs": [],
            "error": {"type": "syntax", "message": str(e), "traceback": ""},
        }

    # Restore state
    position, open_orders, portfolio, user_state = _restore_state(payload.get("state", {}))
    history = [_parse_candle(c) for c in payload.get("history", [])]
    candle = _parse_candle(payload["candle"])
    params = payload.get("params", {})

    # Execute user code in sandboxed namespace
    try:
        from app.strategy_sdk.sandbox import SafeImporter

        # Handle __builtins__ being either a dict or module
        if isinstance(__builtins__, dict):
            safe_builtins = {**__builtins__, "__import__": SafeImporter()}
        else:
            safe_builtins = {**vars(__builtins__), "__import__": SafeImporter()}

        # Create a fake 'strategy_sdk' module so `from strategy_sdk import ...` works
        strategy_sdk_module = types.ModuleType("strategy_sdk")
        strategy_sdk_module.AlgoMatterStrategy = AlgoMatterStrategy
        strategy_sdk_module.Candle = Candle
        sys.modules["strategy_sdk"] = strategy_sdk_module

        namespace = {
            "__builtins__": safe_builtins,
            "AlgoMatterStrategy": AlgoMatterStrategy,
            "Candle": Candle,
        }
        exec(code, namespace)

        strategy_cls = namespace.get(entrypoint)
        if strategy_cls is None:
            return {
                "orders": [], "cancelled_orders": [], "state": {"user_state": user_state},
                "logs": [],
                "error": {"type": "runtime", "message": f"Class '{entrypoint}' not found in strategy code", "traceback": ""},
            }

        strategy = strategy_cls(
            params=params,
            state=user_state,
            position=position,
            portfolio=portfolio,
            open_orders=open_orders,
            history=history,
        )

        strategy.on_init()

        # Process order updates before candle
        for update in payload.get("order_updates", []):
            strategy.on_order_update(
                order_id=update["order_id"],
                status=update["status"],
                fill_price=update.get("fill_price"),
                fill_quantity=update.get("fill_quantity"),
            )

        strategy.on_candle(candle)

        # collect_output returns "state" as raw user_state dict
        # We need to wrap it in {"user_state": ...} for the subprocess protocol
        output = strategy.collect_output()
        output["state"] = {"user_state": output["state"]}
        return output

    except Exception as e:
        tb = traceback.format_exc()
        return {
            "orders": [], "cancelled_orders": [],
            "state": {"user_state": user_state},
            "logs": [],
            "error": {"type": "runtime", "message": f"{type(e).__name__}: {e}", "traceback": tb},
        }


def run_from_stdin_payload():
    """Entry point for subprocess: read JSON from stdin, write result to stdout."""
    payload = json.loads(sys.stdin.read())
    result = run_tick(payload)
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()


if __name__ == "__main__":
    run_from_stdin_payload()
