export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const POLLING_INTERVALS = {
  DASHBOARD: 10_000,
  SIGNALS: 5_000,
  PAPER_TRADING: 10_000,
  HEALTH: 30_000,
  BACKTEST_STATUS: 2_000,
} as const;
