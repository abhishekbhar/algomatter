import sys

from pydantic_settings import BaseSettings

_INSECURE_DEFAULTS = {"change-me", "secret", "password", ""}


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://algomatter:algomatter@localhost:5432/algomatter"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    master_key: str = "change-me"
    rate_limit_per_minute: int = 60
    max_webhook_payload_bytes: int = 65536
    enable_paper_trading: bool = True
    enable_backtesting: bool = True

    model_config = {"env_prefix": "ALGOMATTER_", "env_file": ".env"}


settings = Settings()

# Fail fast in production if secrets are still set to insecure defaults.
# In tests/dev the env var ALGOMATTER_SKIP_SECRET_CHECK=1 bypasses this.
import os as _os  # noqa: E402
if not _os.getenv("ALGOMATTER_SKIP_SECRET_CHECK"):
    _errors = []
    if settings.jwt_secret in _INSECURE_DEFAULTS or len(settings.jwt_secret) < 32:
        _errors.append("ALGOMATTER_JWT_SECRET must be set to a random string of at least 32 characters")
    if settings.master_key in _INSECURE_DEFAULTS or len(settings.master_key) < 32:
        _errors.append("ALGOMATTER_MASTER_KEY must be set to a random string of at least 32 characters")
    if _errors:
        print("FATAL: Insecure configuration detected:", file=sys.stderr)
        for _e in _errors:
            print(f"  - {_e}", file=sys.stderr)
        sys.exit(1)
