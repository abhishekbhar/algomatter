import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BrokerOrdersTable } from "@/components/brokers/BrokerOrdersTable";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");

const mockOrder = {
  order_id: "ord-1",
  deployment_id: "dep-1",
  deployment_name: "BTC Strategy",
  symbol: "BTCUSDT",
  action: "BUY",
  quantity: 0.1,
  order_type: "LIMIT",
  price: 82000,
  created_at: "2026-04-06T10:00:00Z",
};

describe("BrokerOrdersTable", () => {
  it("renders order row", () => {
    (useApiModule.useBrokerOrders as jest.Mock).mockReturnValue({ data: [mockOrder], isLoading: false });
    render(<ChakraProvider><BrokerOrdersTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("LIMIT")).toBeInTheDocument();
    expect(screen.getByText("BTC Strategy")).toBeInTheDocument();
  });

  it("renders empty state when no orders", () => {
    (useApiModule.useBrokerOrders as jest.Mock).mockReturnValue({ data: [], isLoading: false });
    render(<ChakraProvider><BrokerOrdersTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/no open orders/i)).toBeInTheDocument();
  });

  it("shows MKT for market orders with no price", () => {
    (useApiModule.useBrokerOrders as jest.Mock).mockReturnValue({
      data: [{ ...mockOrder, order_type: "MARKET", price: null }],
      isLoading: false,
    });
    render(<ChakraProvider><BrokerOrdersTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText("MKT")).toBeInTheDocument();
  });
});
