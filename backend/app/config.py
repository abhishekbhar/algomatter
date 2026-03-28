from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://algomatter:algomatter@localhost:5432/algomatter"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    master_key: str = "change-me"
    rate_limit_per_minute: int = 60
    max_webhook_payload_bytes: int = 65536

    model_config = {"env_prefix": "ALGOMATTER_", "env_file": ".env"}


settings = Settings()
