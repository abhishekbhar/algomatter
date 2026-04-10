from arq import cron
from arq.connections import RedisSettings

from app.backtesting.tasks import run_backtest_task
from app.config import settings
from app.historical.tasks import daily_data_fetch


class WorkerSettings:
    functions = [run_backtest_task]
    cron_jobs = [cron(daily_data_fetch, hour=6, minute=0)]  # 6 AM daily
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 100          # up from 10 — allows burst of concurrent tasks
    job_timeout = 3600      # 1 hour max per job — prevents hung backtests blocking queue
    keep_result_forever = False
    result_ttl = 86400      # store results for 24 h then auto-expire from Redis
