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
    strategy_name: str
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


class ManualOrderRequest(BaseModel):
    action: str
    quantity: float
    order_type: str = "market"
    price: float | None = None
    trigger_price: float | None = None
    take_profit: float | None = None
    stop_loss: float | None = None


class CancelOrderRequest(BaseModel):
    order_id: str


class DeploymentTradeResponse(BaseModel):
    id: str
    deployment_id: str
    order_id: str
    broker_order_id: str | None
    action: str
    quantity: float
    order_type: str
    price: float | None
    trigger_price: float | None
    fill_price: float | None
    fill_quantity: float | None
    status: str
    is_manual: bool
    realized_pnl: float | None
    created_at: str
    filled_at: str | None
    strategy_name: str
    symbol: str


class TradesResponse(BaseModel):
    trades: list[DeploymentTradeResponse]
    total: int
    offset: int
    limit: int


class RecentTradesResponse(BaseModel):
    trades: list[DeploymentTradeResponse]
    total: int


class PositionResponse(BaseModel):
    deployment_id: str
    position: dict | None
    portfolio: dict
    open_orders: list
    open_orders_count: int
    total_realized_pnl: float


class MetricsResponse(BaseModel):
    total_return: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    avg_trade_pnl: float
    best_trade: float | None
    worst_trade: float | None


class ComparisonResponse(BaseModel):
    backtest: dict
    current: dict
    deltas: dict
    backtest_deployment_id: str
    promotion_chain: list[str]


class AggregateStatsResponse(BaseModel):
    total_deployed_capital: float
    aggregate_pnl: float
    aggregate_pnl_pct: float
    active_deployments: int
    todays_trades: int


class StopAllResponse(BaseModel):
    deployments: list[DeploymentResponse]
    orders_cancelled: int
