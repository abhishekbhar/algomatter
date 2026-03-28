import logging
import uuid
from datetime import datetime, timezone

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db.models import StrategyDeployment
from app.db.session import async_session_factory
from app.strategy_runner.tick_runner import run_tick

logger = logging.getLogger(__name__)

_scheduler: AsyncScheduler | None = None
_scheduler_ctx = None
_registered_jobs: dict[str, str] = {}  # deployment_id -> job_id


async def start_scheduler() -> AsyncScheduler:
    """Start the APScheduler v4 scheduler using async context manager."""
    global _scheduler, _scheduler_ctx
    if _scheduler is None:
        _scheduler = AsyncScheduler()
        await _scheduler.__aenter__()
        await _scheduler.start_in_background()
        logger.info("APScheduler started in background")
    return _scheduler


async def stop_scheduler() -> None:
    """Stop the scheduler cleanly."""
    global _scheduler, _scheduler_ctx
    if _scheduler is not None:
        await _scheduler.__aexit__(None, None, None)
        _scheduler = None
        _scheduler_ctx = None


async def _tick_job(deployment_id: str):
    """Job function called by APScheduler."""
    async with async_session_factory() as session:
        await run_tick(uuid.UUID(deployment_id), session)


async def register_deployment(deployment_id: str, cron_expression: str) -> None:
    """Register a cron job for a deployment and mark it as running."""
    if _scheduler is None:
        await start_scheduler()

    parts = cron_expression.strip().split()
    if len(parts) != 5:
        logger.error(f"Invalid cron expression: {cron_expression}")
        return

    trigger = CronTrigger(
        minute=parts[0], hour=parts[1], day=parts[2],
        month=parts[3], day_of_week=parts[4],
    )

    job_id = f"deployment_{deployment_id}"
    await _scheduler.add_schedule(
        _tick_job, trigger, id=job_id, args=[deployment_id],
        conflict_policy="replace",
    )
    _registered_jobs[deployment_id] = job_id

    # Update deployment status to running
    async with async_session_factory() as session:
        deployment = await session.get(StrategyDeployment, uuid.UUID(deployment_id))
        if deployment and deployment.status == "pending":
            deployment.status = "running"
            deployment.started_at = datetime.now(timezone.utc)
            await session.commit()

    logger.info(f"Registered cron job for deployment {deployment_id}: {cron_expression}")


async def unregister_deployment(deployment_id: str) -> None:
    """Remove a cron job for a deployment."""
    if _scheduler is None:
        return
    job_id = _registered_jobs.pop(deployment_id, f"deployment_{deployment_id}")
    try:
        await _scheduler.remove_schedule(job_id)
        logger.info(f"Unregistered cron job for deployment {deployment_id}")
    except Exception as e:
        logger.warning(f"Could not remove schedule {job_id}: {e}")


async def load_active_deployments() -> None:
    """On startup, load all running deployments and register their cron jobs."""
    await start_scheduler()

    async with async_session_factory() as session:
        result = await session.execute(
            select(StrategyDeployment).where(
                StrategyDeployment.status.in_(["running", "pending"]),
                StrategyDeployment.mode.in_(["paper", "live"]),
                StrategyDeployment.cron_expression.isnot(None),
                StrategyDeployment.cron_expression != "",
            )
        )
        deployments = result.scalars().all()
        for d in deployments:
            await register_deployment(str(d.id), d.cron_expression)
        logger.info(f"Loaded {len(deployments)} active deployments")
