import secrets
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    webhook_token: Mapped[str] = mapped_column(
        String(64), default=lambda: secrets.token_urlsafe(32)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    __table_args__ = (
        Index(
            "ix_broker_connections_tenant_label",
            "tenant_id",
            "label",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    broker_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    credentials: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("broker_connections.id"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(50), default="paper")
    mapping_template: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WebhookSignal(Base):
    __tablename__ = "webhook_signals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategies.id"), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    parsed_signal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rule_result: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rule_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_result: Mapped[str | None] = mapped_column(String(50), nullable=True)
    execution_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    processing_ms: Mapped[int | None] = mapped_column(nullable=True)


class HistoricalOHLCV(Base):
    __tablename__ = "historical_ohlcv"

    symbol: Mapped[str] = mapped_column(String(50), primary_key=True)
    exchange: Mapped[str] = mapped_column(String(50), primary_key=True)
    interval: Mapped[str] = mapped_column(String(10), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    open: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)


class StrategyResult(Base):
    __tablename__ = "strategy_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategies.id"), nullable=True
    )
    deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategy_deployments.id", ondelete="CASCADE"), nullable=True
    )
    strategy_code_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategy_code_versions.id", ondelete="CASCADE"), nullable=True
    )
    result_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trade_log: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    equity_curve: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PaperTradingSession(Base):
    __tablename__ = "paper_trading_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategies.id"), nullable=True
    )
    strategy_code_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategy_codes.id"), nullable=True
    )
    initial_capital: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    current_balance: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_trading_sessions.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    avg_entry_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    current_price: Mapped[float | None] = mapped_column(
        Numeric(20, 8), nullable=True
    )
    unrealized_pnl: Mapped[float | None] = mapped_column(
        Numeric(20, 8), nullable=True
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_trading_sessions.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("webhook_signals.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    fill_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    commission: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    slippage: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    realized_pnl: Mapped[float | None] = mapped_column(
        Numeric(20, 8), nullable=True
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StrategyCode(Base):
    __tablename__ = "strategy_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    entrypoint: Mapped[str] = mapped_column(String(100), default="Strategy")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    versions: Mapped[list["StrategyCodeVersion"]] = relationship(
        back_populates="strategy_code", passive_deletes=True
    )
    deployments: Mapped[list["StrategyDeployment"]] = relationship(
        back_populates="strategy_code", passive_deletes=True
    )


class StrategyCodeVersion(Base):
    __tablename__ = "strategy_code_versions"
    __table_args__ = (
        UniqueConstraint("strategy_code_id", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    strategy_code_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_codes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    strategy_code: Mapped["StrategyCode"] = relationship(
        back_populates="versions"
    )


class StrategyDeployment(Base):
    __tablename__ = "strategy_deployments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    strategy_code_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_codes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy_code_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_code_versions.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), default="DELIVERY")
    interval: Mapped[str] = mapped_column(String(10), nullable=False)
    broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("broker_connections.id"), nullable=True
    )
    cron_expression: Mapped[str | None] = mapped_column(String(50), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    promoted_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategy_deployments.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    strategy_code: Mapped["StrategyCode"] = relationship(
        back_populates="deployments"
    )
    code_version: Mapped["StrategyCodeVersion"] = relationship()
    state: Mapped["DeploymentState | None"] = relationship(
        back_populates="deployment", uselist=False, passive_deletes=True
    )
    trades: Mapped[list["DeploymentTrade"]] = relationship(
        back_populates="deployment", passive_deletes=True
    )


class DeploymentState(Base):
    __tablename__ = "deployment_states"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_deployments.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    position: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    open_orders: Mapped[dict] = mapped_column(JSON, default=list)
    portfolio: Mapped[dict] = mapped_column(JSON, default=dict)
    user_state: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    deployment: Mapped["StrategyDeployment"] = relationship(
        back_populates="state"
    )


class DeploymentLog(Base):
    __tablename__ = "deployment_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_deployments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    level: Mapped[str] = mapped_column(String(10), default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)


class ExchangeInstrument(Base):
    __tablename__ = "exchange_instruments"
    __table_args__ = (UniqueConstraint("exchange", "symbol", "product_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(20), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(20), nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class DeploymentTrade(Base):
    __tablename__ = "deployment_trades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[str] = mapped_column(String(32), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric, nullable=False)
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    trigger_price: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fill_price: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fill_quantity: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")
    is_manual: Mapped[bool] = mapped_column(default=False)
    realized_pnl: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    filled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    deployment: Mapped["StrategyDeployment"] = relationship(back_populates="trades")


class ManualTrade(Base):
    """Standalone manual trade — not tied to any deployment."""
    __tablename__ = "manual_trades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    broker_connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("broker_connections.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    product_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    trigger_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    leverage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_model: Mapped[str | None] = mapped_column(String(16), nullable=True)
    position_side: Mapped[str | None] = mapped_column(String(16), nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fill_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="submitted")
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    broker_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
