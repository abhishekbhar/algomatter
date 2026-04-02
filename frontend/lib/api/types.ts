// Shared TypeScript interfaces matching backend Pydantic models

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  plan: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Strategy {
  id: string;
  name: string;
  broker_connection_id: string | null;
  mode: string;
  mapping_template: Record<string, unknown> | null;
  rules: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}

export interface WebhookConfig {
  webhook_url: string;
  token: string;
}

export interface WebhookSignal {
  id: string;
  strategy_id: string;
  strategy_name?: string;
  raw_payload: Record<string, unknown>;
  parsed_signal: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
  execution_result: string | null;
  execution_detail: {
    order_id?: string;
    broker_order_id?: string;
    status?: string;
    fill_price?: string;
    fill_quantity?: string;
    message?: string;
    placed_at?: string;
    error?: string;
  } | null;
  processing_ms: number | null;
  received_at: string;
}

export interface BrokerConnection {
  id: string;
  broker_type: string;
  is_active: boolean;
  connected_at: string;
}

export interface PaperSession {
  id: string;
  strategy_id: string;
  initial_capital: string;
  current_balance: string;
  status: string;
  started_at: string | null;
  stopped_at: string | null;
}

export interface PaperPosition {
  id: string;
  symbol: string;
  exchange: string;
  side: string;
  quantity: string;
  avg_entry_price: string;
  current_price: string | null;
  unrealized_pnl: string | null;
  opened_at: string | null;
  closed_at: string | null;
}

export interface PaperTrade {
  id: string;
  symbol: string;
  exchange: string;
  action: string;
  quantity: string;
  fill_price: string;
  commission: string;
  slippage: string;
  realized_pnl: string | null;
  executed_at: string | null;
}

export interface PaperSessionDetail extends PaperSession {
  positions: PaperPosition[];
  trades: PaperTrade[];
}

export interface BacktestResult {
  id: string;
  strategy_id: string | null;
  strategy_name: string | null;
  status: string;
  trade_log: Array<Record<string, unknown>> | null;
  equity_curve: Array<Record<string, unknown>> | null;
  metrics: Record<string, unknown> | null;
  config: Record<string, unknown> | null;
  warnings: string[] | null;
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface AnalyticsOverview {
  total_pnl: number;
  active_strategies: number;
  open_positions: number;
  trades_today: number;
}

export interface StrategyMetrics {
  total_return: number;
  win_rate: number;
  profit_factor: number;
  sharpe_ratio: number;
  max_drawdown: number;
  total_trades: number;
  avg_trade_pnl: number;
}

export interface EquityCurvePoint {
  timestamp: string;
  equity: number;
}

export interface AnalyticsTrade {
  timestamp: string;
  symbol: string;
  action: string;
  quantity: number;
  fill_price: number | null;
  status: string;
  pnl: number;
}

export interface HealthStatus {
  status: string;
}

// Hosted Strategies
export interface HostedStrategy {
  id: string;
  name: string;
  description: string | null;
  code: string;
  version: number;
  entrypoint: string;
  created_at: string;
  updated_at: string;
}

export interface StrategyVersion {
  id: string;
  version: number;
  code: string;
  created_at: string;
}

export interface StrategyTemplate {
  name: string;
  description: string;
  code: string;
  params: Record<string, unknown>;
}

// Deployments
export interface Deployment {
  id: string;
  strategy_name: string;
  strategy_code_id: string;
  strategy_code_version_id: string;
  mode: "backtest" | "paper" | "live";
  status: "pending" | "running" | "paused" | "stopped" | "completed" | "failed";
  symbol: string;
  exchange: string;
  product_type: string;
  interval: string;
  broker_connection_id: string | null;
  cron_expression: string | null;
  config: Record<string, unknown>;
  params: Record<string, unknown>;
  promoted_from_id: string | null;
  created_at: string;
  started_at: string | null;
  stopped_at: string | null;
}

export interface DeploymentResult {
  id: string;
  deployment_id: string;
  trade_log: unknown[] | null;
  equity_curve: { timestamp: string; equity: number }[] | null;
  metrics: StrategyMetrics | null;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface DeploymentLogEntry {
  id: string;
  timestamp: string;
  level: string;
  message: string;
}

export interface DeploymentLogsResponse {
  logs: DeploymentLogEntry[];
  total: number;
  offset: number;
  limit: number;
}

// Live Trading
export interface DeploymentTrade {
  id: string;
  deployment_id: string;
  order_id: string;
  broker_order_id: string | null;
  action: string;
  quantity: number;
  order_type: string;
  price: number | null;
  trigger_price: number | null;
  fill_price: number | null;
  fill_quantity: number | null;
  status: string;
  is_manual: boolean;
  realized_pnl: number | null;
  created_at: string;
  filled_at: string | null;
  strategy_name: string;
  symbol: string;
}

export interface TradesResponse {
  trades: DeploymentTrade[];
  total: number;
  offset: number;
  limit: number;
}

export interface RecentTradesResponse {
  trades: DeploymentTrade[];
  total: number;
}

export interface PositionInfo {
  deployment_id: string;
  position: { quantity: number; avg_entry_price: number; unrealized_pnl: number } | null;
  portfolio: { balance: number; equity: number; available_margin: number };
  open_orders: { id: string; action: string; quantity: number; order_type?: string; price?: number }[];
  open_orders_count: number;
  total_realized_pnl: number;
}

export interface LiveMetrics {
  total_return: number;
  win_rate: number;
  profit_factor: number;
  sharpe_ratio: number;
  max_drawdown: number;
  total_trades: number;
  avg_trade_pnl: number;
  best_trade: number | null;
  worst_trade: number | null;
}

export interface ComparisonData {
  backtest: LiveMetrics;
  current: LiveMetrics;
  deltas: Record<string, number>;
  backtest_deployment_id: string;
  promotion_chain: string[];
}

export interface AggregateStats {
  total_deployed_capital: number;
  aggregate_pnl: number;
  aggregate_pnl_pct: number;
  active_deployments: number;
  todays_trades: number;
}

export interface StopAllResponse {
  deployments: Deployment[];
  orders_cancelled: number;
}

// Market Data
export interface OhlcvCandle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TradeMarker {
  time: string;
  price: number;
  action: "BUY" | "SELL";
}
