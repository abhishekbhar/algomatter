import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StrategyDeployment, StrategyCode, StrategyCodeVersion, DeploymentState, DeploymentLog
from app.historical.binance import fetch_latest_candles
from app.strategy_runner.executor import run_subprocess
from app.strategy_runner.order_router import dispatch_orders

logger = logging.getLogger(__name__)


async def run_tick(deployment_id: uuid.UUID, session: AsyncSession) -> dict:
    """Process one tick for a deployment."""
    deployment = await session.get(StrategyDeployment, deployment_id)
    if not deployment or deployment.status != "running":
        return {"error": "deployment_not_running"}

    # Load code version
    code_version = await session.get(StrategyCodeVersion, deployment.strategy_code_version_id)
    if not code_version:
        return {"error": "code_version_not_found"}

    # Get entrypoint from StrategyCode
    strategy_code = await session.get(StrategyCode, deployment.strategy_code_id)
    entrypoint = strategy_code.entrypoint if strategy_code else "Strategy"

    # Load state
    state = await session.get(DeploymentState, deployment_id)
    if not state:
        return {"error": "state_not_found"}

    # Initialize portfolio if empty (first tick)
    if not state.portfolio or not state.portfolio.get("balance"):
        config = deployment.config or {}
        capital = float(config.get("capital") or config.get("initial_capital", 10000))
        state.portfolio = {
            "balance": capital,
            "equity": capital,
            "available_margin": capital,
        }
        await session.commit()
        logger.info(f"Initialized portfolio for {deployment_id} with capital {capital}")

    # Fetch latest candles from Binance
    try:
        candles = await fetch_latest_candles(
            symbol=deployment.symbol,
            interval=deployment.interval,
            limit=50,
        )
    except Exception as e:
        logger.error(f"Failed to fetch candles for {deployment_id}: {e}")
        return {"error": f"candle_fetch_failed: {e}"}

    if not candles:
        logger.warning(f"No candles returned for deployment {deployment_id}")
        return {"error": "no_candles"}

    # Latest closed candle is the current tick, rest is history
    current_candle = candles[-1]
    history = candles[:-1]

    logger.info(f"Tick for {deployment_id}: {deployment.symbol} {deployment.interval} candle @ {current_candle['timestamp']}")

    # Build subprocess payload
    payload = {
        "code": code_version.code,
        "entrypoint": entrypoint,
        "candle": current_candle,
        "history": history,
        "state": {
            "position": state.position,
            "open_orders": state.open_orders,
            "portfolio": state.portfolio,
            "user_state": state.user_state,
        },
        "order_updates": [],
        "params": deployment.params,
        "mode": deployment.mode,
    }

    # Execute strategy
    result = await run_subprocess(payload)

    # Log entries
    for log_entry in result.get("logs", []):
        log = DeploymentLog(
            tenant_id=deployment.tenant_id,
            deployment_id=deployment_id,
            level=log_entry.get("level", "info"),
            message=log_entry.get("message", ""),
        )
        session.add(log)

    # Handle errors
    if result.get("error"):
        error = result["error"]
        error_log = DeploymentLog(
            tenant_id=deployment.tenant_id,
            deployment_id=deployment_id,
            level="error",
            message=f"[{error['type']}] {error['message']}",
        )
        session.add(error_log)
        await session.commit()
        return {"error": error}

    # Dispatch orders
    order_results = await dispatch_orders(result.get("orders", []), deployment, session)

    # Update state
    new_state = result.get("state", {})
    state.user_state = new_state.get("user_state", state.user_state)
    state.updated_at = datetime.now(timezone.utc)

    await session.commit()

    return {"success": True, "orders_dispatched": len(order_results)}
