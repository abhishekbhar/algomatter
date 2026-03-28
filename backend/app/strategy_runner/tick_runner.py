import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StrategyDeployment, StrategyCodeVersion, DeploymentState, DeploymentLog
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

    # Load state
    state = await session.get(DeploymentState, deployment_id)
    if not state:
        return {"error": "state_not_found"}

    # TODO: Fetch latest candle + history from broker
    # For now, this will be populated by the scheduler when it calls this function
    # The candle data should be passed in or fetched here

    # Build subprocess payload
    payload = {
        "code": code_version.code,
        "entrypoint": "Strategy",  # Could be stored on StrategyCode
        "candle": {},  # To be filled by caller or fetched
        "history": [],  # To be filled
        "state": {
            "position": state.position,
            "open_orders": state.open_orders,
            "portfolio": state.portfolio,
            "user_state": state.user_state,
        },
        "order_updates": [],  # To be filled with pending order status updates
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
