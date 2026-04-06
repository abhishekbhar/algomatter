import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";

jest.mock("@/lib/hooks/useManualTrades", () => ({
  useManualTrades: jest.fn(),
  useOpenManualTrades: jest.fn(),
}));
jest.mock("@/lib/api/client", () => ({ apiClient: jest.fn() }));

import { TradeHistory } from "@/components/trade/TradeHistory";
import * as hooks from "@/lib/hooks/useManualTrades";

describe("TradeHistory", () => {
  it("renders empty state for open orders", () => {
    (hooks.useOpenManualTrades as jest.Mock).mockReturnValue({ data: { trades: [], total: 0, offset: 0, limit: 100 }, mutate: jest.fn() });
    (hooks.useManualTrades as jest.Mock).mockReturnValue({ data: { trades: [], total: 0, offset: 0, limit: 50 }, mutate: jest.fn() });
    render(<ChakraProvider><TradeHistory /></ChakraProvider>);
    expect(screen.getByText(/no open orders/i)).toBeInTheDocument();
  });

  it("renders trade row", () => {
    (hooks.useOpenManualTrades as jest.Mock).mockReturnValue({
      data: { trades: [{ id: "t1", symbol: "BTCUSDT", action: "BUY", order_type: "LIMIT", price: 82000, quantity: 0.05, fill_price: null, fill_quantity: null, status: "open", created_at: "2026-04-06T10:00:00Z" }], total: 1, offset: 0, limit: 100 },
      mutate: jest.fn(),
    });
    (hooks.useManualTrades as jest.Mock).mockReturnValue({ data: { trades: [], total: 0, offset: 0, limit: 50 }, mutate: jest.fn() });
    render(<ChakraProvider><TradeHistory /></ChakraProvider>);
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });
});
