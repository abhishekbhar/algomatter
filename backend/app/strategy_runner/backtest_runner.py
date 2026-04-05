import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StrategyDeployment, StrategyCodeVersion, StrategyResult, StrategyCode
from app.db.session import async_session_factory
from app.historical.downloader import ensure_candles

logger = logging.getLogger(__name__)


def _parse_date(s: str) -> datetime:
    """Parse YYYY-MM-DD to timezone-aware datetime."""
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


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

            config = deployment.config or {}
            initial_capital = config.get("initial_capital") or config.get("capital", 100000)
            start_date = config.get("start_date", "2025-01-01")
            end_date = config.get("end_date", "2025-06-01")

            # Fetch candles — downloads from Binance if not cached in DB
            candles = await ensure_candles(
                symbol=deployment.symbol,
                interval=deployment.interval,
                start=_parse_date(start_date),
                end=_parse_date(end_date),
                exchange=deployment.exchange,
            )
            logger.info(f"Loaded {len(candles)} candles for backtest {deployment_id}")

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
                strategy_id=None,
                deployment_id=deployment_id,
                strategy_code_version_id=deployment.strategy_code_version_id,
                result_type="backtest",
                status="completed",
                trade_log=results.get("trade_log", []),
                equity_curve=results.get("equity_curve", []),
                metrics=results.get("metrics", {}),
                config={
                    "start_date": start_date,
                    "end_date": end_date,
                    "capital": initial_capital,
                    "symbol": deployment.symbol,
                    "exchange": deployment.exchange,
                    "interval": deployment.interval,
                    "params": deployment.params,
                    "candles_loaded": len(candles),
                },
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
