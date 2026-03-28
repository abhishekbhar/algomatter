import asyncio
import json
import logging
import signal
import uuid

from redis.asyncio import Redis

from app.config import settings
from app.strategy_runner.backtest_runner import run_backtest_job
from app.strategy_runner.scheduler import load_active_deployments, register_deployment, unregister_deployment

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("strategy_runner")

_shutdown = asyncio.Event()


async def _process_queue(redis: Redis):
    """Process backtest jobs from Redis queue."""
    while not _shutdown.is_set():
        try:
            result = await redis.brpop("strategy-runner:queue", timeout=1)
            if result is None:
                continue
            _, data = result
            msg = json.loads(data)
            deployment_id = uuid.UUID(msg["deployment_id"])
            job_type = msg.get("type", "backtest")

            if job_type == "backtest":
                logger.info(f"Processing backtest job for deployment {deployment_id}")
                await run_backtest_job(deployment_id)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error processing queue: {e}")
            await asyncio.sleep(1)


async def _listen_deployments(redis: Redis):
    """Listen for deployment register/unregister commands via pub/sub."""
    pubsub = redis.pubsub()
    await pubsub.subscribe("strategy-runner:deployments")

    try:
        async for message in pubsub.listen():
            if _shutdown.is_set():
                break
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
                action = data.get("action")
                deployment_id = data.get("deployment_id")

                if action == "register":
                    cron_expression = data.get("cron_expression", "*/5 * * * *")
                    await register_deployment(deployment_id, cron_expression)
                elif action == "unregister":
                    await unregister_deployment(deployment_id)

            except Exception as e:
                logger.error(f"Error processing deployment command: {e}")
    finally:
        await pubsub.unsubscribe("strategy-runner:deployments")


async def main():
    logger.info("Strategy runner starting...")

    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    # Load active deployments on startup
    await load_active_deployments()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown.set)

    # Run queue processor and pub/sub listener concurrently
    tasks = [
        asyncio.create_task(_process_queue(redis)),
        asyncio.create_task(_listen_deployments(redis)),
    ]

    logger.info("Strategy runner started. Listening for jobs...")
    await _shutdown.wait()

    logger.info("Shutting down...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await redis.aclose()
    logger.info("Strategy runner stopped.")


if __name__ == "__main__":
    asyncio.run(main())
