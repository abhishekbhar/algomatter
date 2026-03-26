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
