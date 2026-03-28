"use client";
import useSWR, { SWRConfiguration } from "swr";
import { apiClient } from "@/lib/api/client";
import { POLLING_INTERVALS } from "@/lib/utils/constants";
import type {
  User,
  HealthStatus,
  Strategy,
  WebhookConfig,
  WebhookSignal,
  BrokerConnection,
  PaperSession,
  PaperSessionDetail,
  BacktestResult,
  AnalyticsOverview,
  StrategyMetrics,
  EquityCurvePoint,
  AnalyticsTrade,
  HostedStrategy,
  StrategyVersion,
  StrategyTemplate,
  Deployment,
  DeploymentResult,
  DeploymentLogsResponse,
  AggregateStats,
  RecentTradesResponse,
  TradesResponse,
  PositionInfo,
  LiveMetrics,
  ComparisonData,
} from "@/lib/api/types";

function fetcher<T>(path: string): Promise<T> {
  return apiClient<T>(path);
}

function useApiGet<T>(path: string | null, config?: SWRConfiguration) {
  return useSWR<T>(path, fetcher, config);
}

export function useMe() {
  return useApiGet<User>("/api/v1/auth/me");
}

export function useHealth() {
  return useApiGet<HealthStatus>("/api/v1/health", {
    refreshInterval: POLLING_INTERVALS.HEALTH,
  });
}

export function useStrategies() {
  return useApiGet<Strategy[]>("/api/v1/strategies");
}

export function useAllStrategies() {
  const { data: webhook } = useStrategies();
  const { data: hosted } = useHostedStrategies();
  const all = [
    ...(webhook ?? []).map((s) => ({ id: s.id, name: s.name, type: "webhook" as const })),
    ...(hosted ?? []).map((s) => ({ id: s.id, name: s.name, type: "hosted" as const })),
  ];
  return all;
}

export function useStrategy(id: string | null) {
  return useApiGet<Strategy>(id ? `/api/v1/strategies/${id}` : null);
}

export function useWebhookConfig() {
  return useApiGet<WebhookConfig>("/api/v1/webhooks/config");
}

export function useWebhookSignals() {
  return useApiGet<WebhookSignal[]>("/api/v1/webhooks/signals", {
    refreshInterval: POLLING_INTERVALS.SIGNALS,
  });
}

export function useBrokers() {
  return useApiGet<BrokerConnection[]>("/api/v1/brokers");
}

export function usePaperSessions() {
  return useApiGet<PaperSession[]>("/api/v1/paper-trading/sessions");
}

export function usePaperSession(id: string | null) {
  return useApiGet<PaperSessionDetail>(
    id ? `/api/v1/paper-trading/sessions/${id}` : null,
    { refreshInterval: POLLING_INTERVALS.PAPER_TRADING },
  );
}

export function useBacktests() {
  return useApiGet<BacktestResult[]>("/api/v1/backtests");
}

export function useBacktest(id: string | null) {
  return useApiGet<BacktestResult>(id ? `/api/v1/backtests/${id}` : null);
}

export function useAnalyticsOverview() {
  return useApiGet<AnalyticsOverview>("/api/v1/analytics/overview", {
    refreshInterval: POLLING_INTERVALS.DASHBOARD,
  });
}

export function useStrategyMetrics(strategyId: string | null) {
  return useApiGet<StrategyMetrics>(
    strategyId ? `/api/v1/analytics/strategies/${strategyId}/metrics` : null,
  );
}

export function useStrategyEquityCurve(strategyId: string | null) {
  return useApiGet<EquityCurvePoint[]>(
    strategyId
      ? `/api/v1/analytics/strategies/${strategyId}/equity-curve`
      : null,
  );
}

export function useStrategyTrades(strategyId: string | null) {
  return useApiGet<AnalyticsTrade[]>(
    strategyId ? `/api/v1/analytics/strategies/${strategyId}/trades` : null,
  );
}

// Hosted Strategies
export function useHostedStrategies() {
  return useApiGet<HostedStrategy[]>("/api/v1/hosted-strategies");
}

export function useHostedStrategy(id: string | undefined) {
  return useApiGet<HostedStrategy>(id ? `/api/v1/hosted-strategies/${id}` : null);
}

export function useStrategyVersions(id: string | undefined) {
  return useApiGet<StrategyVersion[]>(id ? `/api/v1/hosted-strategies/${id}/versions` : null);
}

export function useStrategyTemplates() {
  return useApiGet<StrategyTemplate[]>("/api/v1/strategy-templates");
}

// Deployments
export function useDeployments(strategyId: string | undefined) {
  return useApiGet<Deployment[]>(
    strategyId ? `/api/v1/hosted-strategies/${strategyId}/deployments` : null,
    { refreshInterval: POLLING_INTERVALS.PAPER_TRADING }
  );
}

export function useDeployment(id: string | undefined) {
  return useApiGet<Deployment>(id ? `/api/v1/deployments/${id}` : null, { refreshInterval: 2000 });
}

export function useDeploymentResults(id: string | undefined) {
  return useApiGet<DeploymentResult | null>(id ? `/api/v1/deployments/${id}/results` : null);
}

export function useActiveDeployments() {
  const { data: running, ...runningRest } = useApiGet<Deployment[]>(
    "/api/v1/deployments?status=running",
    { refreshInterval: 2000 }
  );
  const { data: paused } = useApiGet<Deployment[]>(
    "/api/v1/deployments?status=paused",
    { refreshInterval: 2000 }
  );
  const data = [...(running ?? []), ...(paused ?? [])];
  return { data: data.length > 0 || running || paused ? data : undefined, ...runningRest };
}

export function useDeploymentLogs(id: string | undefined, offset = 0, limit = 50) {
  return useApiGet<DeploymentLogsResponse>(
    id ? `/api/v1/deployments/${id}/logs?offset=${offset}&limit=${limit}` : null
  );
}

// Live Trading
export function useAggregateStats() {
  return useApiGet<AggregateStats>("/api/v1/deployments/aggregate-stats", { refreshInterval: 2000 });
}

export function useRecentTrades(limit = 20) {
  return useApiGet<RecentTradesResponse>(
    `/api/v1/deployments/recent-trades?limit=${limit}`,
    { refreshInterval: 5000 }
  );
}

export function useDeploymentTrades(id: string | undefined, offset = 0, limit = 50) {
  return useApiGet<TradesResponse>(
    id ? `/api/v1/deployments/${id}/trades?offset=${offset}&limit=${limit}` : null,
    { refreshInterval: 5000 }
  );
}

export function useDeploymentPosition(id: string | undefined) {
  return useApiGet<PositionInfo>(id ? `/api/v1/deployments/${id}/position` : null, { refreshInterval: 2000 });
}

export function useDeploymentMetrics(id: string | undefined) {
  return useApiGet<LiveMetrics>(id ? `/api/v1/deployments/${id}/metrics` : null, { refreshInterval: 10000 });
}

export function useDeploymentComparison(id: string | undefined) {
  return useApiGet<ComparisonData | null>(id ? `/api/v1/deployments/${id}/comparison` : null);
}
