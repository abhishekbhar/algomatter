from pydantic import BaseModel, Field


class CreateDeploymentRequest(BaseModel):
    mode: str  # backtest, paper, live
    symbol: str
    exchange: str
    product_type: str = "DELIVERY"
    interval: str
    broker_connection_id: str | None = None
    cron_expression: str | None = None
    config: dict = Field(default_factory=dict)
    params: dict = Field(default_factory=dict)
    strategy_code_version: int | None = None  # null = latest


class PromoteRequest(BaseModel):
    broker_connection_id: str | None = None
    cron_expression: str | None = None
    config_overrides: dict = Field(default_factory=dict)


class DeploymentResponse(BaseModel):
    id: str
    strategy_code_id: str
    strategy_code_version_id: str
    mode: str
    status: str
    symbol: str
    exchange: str
    product_type: str
    interval: str
    broker_connection_id: str | None
    cron_expression: str | None
    config: dict
    params: dict
    promoted_from_id: str | None
    created_at: str
    started_at: str | None
    stopped_at: str | None


class DeploymentResultResponse(BaseModel):
    id: str
    deployment_id: str
    trade_log: list | None
    equity_curve: list | None
    metrics: dict | None
    status: str
    created_at: str
    completed_at: str | None


class DeploymentLogEntry(BaseModel):
    id: str
    timestamp: str
    level: str
    message: str


class DeploymentLogsResponse(BaseModel):
    logs: list[DeploymentLogEntry]
    total: int
    offset: int
    limit: int
