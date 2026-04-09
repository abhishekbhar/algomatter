/** Credential field names required per broker type. */
export const BROKER_FIELDS: Record<string, string[]> = {
  zerodha: ["api_key", "api_secret", "user_id"],
  exchange1: ["api_key", "private_key"],
  binance_testnet: ["api_key", "api_secret"],
};
