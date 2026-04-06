import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { ManualTradesListResponse } from "@/lib/api/types";

function fetcher<T>(path: string): Promise<T> {
  return apiClient<T>(path);
}

export function useManualTrades(offset = 0, limit = 50, statusFilter?: string) {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (statusFilter) params.set("status_filter", statusFilter);
  return useSWR<ManualTradesListResponse>(`/api/v1/trades/manual?${params}`, fetcher, { refreshInterval: 3000 });
}

export function useOpenManualTrades() {
  return useManualTrades(0, 100, "open");
}
