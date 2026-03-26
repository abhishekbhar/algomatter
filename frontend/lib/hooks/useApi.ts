"use client";
import useSWR, { SWRConfiguration } from "swr";
import { apiClient } from "@/lib/api/client";
import { POLLING_INTERVALS } from "@/lib/utils/constants";

function fetcher<T>(path: string): Promise<T> {
  return apiClient<T>(path);
}

function useApiGet<T>(path: string | null, config?: SWRConfiguration) {
  return useSWR<T>(path, fetcher, config);
}

export function useMe() {
  return useApiGet<{
    id: string;
    email: string;
    is_active: boolean;
    plan: string;
  }>("/api/v1/auth/me");
}

export function useHealth() {
  return useApiGet<{ status: string }>("/api/v1/health", {
    refreshInterval: POLLING_INTERVALS.HEALTH,
  });
}

export function useStrategies() {
  return useApiGet<
    Array<{
      id: string;
      name: string;
      broker_connection_id: string | null;
      mode: string;
      is_active: boolean;
      created_at: string;
      mapping_template: Record<string, unknown> | null;
      rules: Record<string, unknown>;
    }>
  >("/api/v1/strategies");
}

export function useStrategy(id: string | null) {
  return useApiGet(id ? `/api/v1/strategies/${id}` : null);
}

export function useWebhookConfig() {
  return useApiGet<{ webhook_url: string; token: string }>(
    "/api/v1/webhooks/config",
  );
}

export function useWebhookSignals() {
  return useApiGet<Array<Record<string, unknown>>>("/api/v1/webhooks/signals", {
    refreshInterval: POLLING_INTERVALS.SIGNALS,
  });
}

export function useBrokers() {
  return useApiGet<
    Array<{
      id: string;
      broker_type: string;
      is_active: boolean;
      connected_at: string;
    }>
  >("/api/v1/brokers");
}

export function usePaperSessions() {
  return useApiGet<Array<Record<string, unknown>>>(
    "/api/v1/paper-trading/sessions",
  );
}

export function usePaperSession(id: string | null) {
  return useApiGet(
    id ? `/api/v1/paper-trading/sessions/${id}` : null,
    { refreshInterval: POLLING_INTERVALS.PAPER_TRADING },
  );
}

export function useBacktests() {
  return useApiGet<Array<Record<string, unknown>>>("/api/v1/backtests");
}

export function useBacktest(id: string | null) {
  return useApiGet(id ? `/api/v1/backtests/${id}` : null);
}

export function useAnalyticsOverview() {
  return useApiGet<{
    total_pnl: number;
    active_strategies: number;
    open_positions: number;
    trades_today: number;
  }>("/api/v1/analytics/overview", {
    refreshInterval: POLLING_INTERVALS.DASHBOARD,
  });
}

export function useStrategyMetrics(strategyId: string | null) {
  return useApiGet(
    strategyId ? `/api/v1/analytics/strategies/${strategyId}/metrics` : null,
  );
}

export function useStrategyEquityCurve(strategyId: string | null) {
  return useApiGet<Array<Record<string, unknown>>>(
    strategyId
      ? `/api/v1/analytics/strategies/${strategyId}/equity-curve`
      : null,
  );
}

export function useStrategyTrades(strategyId: string | null) {
  return useApiGet<Array<Record<string, unknown>>>(
    strategyId ? `/api/v1/analytics/strategies/${strategyId}/trades` : null,
  );
}
