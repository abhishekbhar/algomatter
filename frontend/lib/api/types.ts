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
  raw_payload: Record<string, unknown>;
  parsed_signal: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
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
