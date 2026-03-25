from arq import cron
from arq.connections import RedisSettings

from app.backtesting.tasks import run_backtest_task
from app.config import settings
from app.historical.tasks import daily_data_fetch


class WorkerSettings:
    functions = [run_backtest_task]
    cron_jobs = [cron(daily_data_fetch, hour=6, minute=0)]  # 6 AM daily
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
