import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BrokerTradesTable } from "@/components/brokers/BrokerTradesTable";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");

const mockTrade = {
  id: "t1", deployment_id: "dep-1", order_id: "o1", broker_order_id: null,
  action: "BUY", quantity: 0.05, order_type: "market", price: null,
  trigger_price: null, fill_price: 83000, fill_quantity: 0.05,
  status: "filled", is_manual: false, realized_pnl: 100,
  created_at: "2026-04-06T09:00:00Z", filled_at: "2026-04-06T09:00:01Z",
  strategy_name: "BTC Strategy", symbol: "BTCUSDT",
};

describe("BrokerTradesTable", () => {
  it("renders trade row", () => {
    (useApiModule.useBrokerTrades as jest.Mock).mockReturnValue({
      data: { trades: [mockTrade], total: 1, offset: 0, limit: 50 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerTradesTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("BTC Strategy")).toBeInTheDocument();
    expect(screen.getByText(/\+\$100/)).toBeInTheDocument();
  });

  it("renders empty state when no trades", () => {
    (useApiModule.useBrokerTrades as jest.Mock).mockReturnValue({
      data: { trades: [], total: 0, offset: 0, limit: 50 }, isLoading: false,
    });
    render(<ChakraProvider><BrokerTradesTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/no trades/i)).toBeInTheDocument();
  });

  it("shows — for null P&L", () => {
    (useApiModule.useBrokerTrades as jest.Mock).mockReturnValue({
      data: { trades: [{ ...mockTrade, realized_pnl: null }], total: 1, offset: 0, limit: 50 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerTradesTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("renders pagination controls when total > limit", () => {
    (useApiModule.useBrokerTrades as jest.Mock).mockReturnValue({
      data: { trades: [mockTrade], total: 100, offset: 0, limit: 50 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerTradesTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
  });
});
