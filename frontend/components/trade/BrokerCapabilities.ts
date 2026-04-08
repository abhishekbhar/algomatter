export interface BrokerCaps {
  spot: boolean;
  futures: boolean;
  orderTypes: string[];
  shortFutures: boolean;
  currency: string;
  currencySymbol: string;
}

export const BROKER_CAPABILITIES: Record<string, BrokerCaps> = {
  exchange1: { spot: true, futures: true, orderTypes: ["MARKET", "LIMIT", "SL", "SL-M"], shortFutures: true, currency: "INR", currencySymbol: "₹" },
  binance_testnet: { spot: true, futures: false, orderTypes: ["MARKET", "LIMIT", "SL", "SL-M"], shortFutures: false, currency: "USDT", currencySymbol: "" },
};

export function getBrokerCaps(brokerType: string): BrokerCaps {
  return BROKER_CAPABILITIES[brokerType] ?? { spot: true, futures: false, orderTypes: ["MARKET", "LIMIT"], shortFutures: false, currency: "USDT", currencySymbol: "" };
}
