import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StrategyDeployment, StrategyCodeVersion, StrategyResult, StrategyCode
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)


async def run_backtest_job(deployment_id: uuid.UUID) -> None:
    """Run a backtest for the given deployment."""
    async with async_session_factory() as session:
        deployment = await session.get(StrategyDeployment, deployment_id)
        if not deployment:
            logger.error(f"Deployment {deployment_id} not found")
            return

        code_version = await session.get(StrategyCodeVersion, deployment.strategy_code_version_id)
        if not code_version:
            logger.error(f"Code version not found for deployment {deployment_id}")
            deployment.status = "failed"
            await session.commit()
            return

        # Get strategy code for entrypoint
        strategy_code = await session.get(StrategyCode, deployment.strategy_code_id)
        entrypoint = strategy_code.entrypoint if strategy_code else "Strategy"

        # Update status to running
        deployment.status = "running"
        deployment.started_at = datetime.now(timezone.utc)
        await session.commit()

        try:
            from app.nautilus_integration.engine import run_backtest

            initial_capital = deployment.config.get("initial_capital", 10000)

            # Placeholder: historical candles would be fetched here
            candles: list[dict] = []

            results = await run_backtest(
                code=code_version.code,
                entrypoint=entrypoint,
                candles=candles,
                symbol=deployment.symbol,
                exchange=deployment.exchange,
                interval=deployment.interval,
                initial_capital=initial_capital,
                params=deployment.params,
            )

            # Save results
            strategy_result = StrategyResult(
                tenant_id=deployment.tenant_id,
                strategy_id=deployment.strategy_code_id,
                deployment_id=deployment_id,
                strategy_code_version_id=deployment.strategy_code_version_id,
                result_type="backtest",
                status="completed",
                trade_log=results.get("trade_log", []),
                equity_curve=results.get("equity_curve", []),
                metrics=results.get("metrics", {}),
                completed_at=datetime.now(timezone.utc),
            )
            session.add(strategy_result)

            deployment.status = "completed"
            deployment.stopped_at = datetime.now(timezone.utc)
            await session.commit()

            logger.info(f"Backtest completed for deployment {deployment_id}")

        except Exception as e:
            logger.error(f"Backtest failed for deployment {deployment_id}: {e}")
            deployment.status = "failed"
            deployment.stopped_at = datetime.now(timezone.utc)
            await session.commit()
