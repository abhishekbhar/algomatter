export interface BrokerCaps {
  spot: boolean;
  futures: boolean;
  orderTypes: string[];
  shortFutures: boolean;
  currency: string;
  currencySymbol: string;
  /** BTC (or base asset) per contract — used for margin/total calculations. Default 1. */
  futuresContractSize: number;
}

export const BROKER_CAPABILITIES: Record<string, BrokerCaps> = {
  exchange1: { spot: true, futures: true, orderTypes: ["MARKET", "LIMIT", "SL", "SL-M"], shortFutures: true, currency: "INR", currencySymbol: "₹", futuresContractSize: 0.001 },
  binance_testnet: { spot: true, futures: false, orderTypes: ["MARKET", "LIMIT", "SL", "SL-M"], shortFutures: false, currency: "USDT", currencySymbol: "", futuresContractSize: 1 },
};

export function getBrokerCaps(brokerType: string): BrokerCaps {
  return BROKER_CAPABILITIES[brokerType] ?? { spot: true, futures: false, orderTypes: ["MARKET", "LIMIT"], shortFutures: false, currency: "USDT", currencySymbol: "", futuresContractSize: 1 };
}
