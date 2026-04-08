import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/lib/api/client", () => ({ apiClient: jest.fn() }));

import { OrderForm } from "@/components/trade/OrderForm";

describe("OrderForm", () => {
  beforeEach(() => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{ id: "b1", broker_type: "exchange1", label: "Main Ex1", is_active: true, connected_at: "2026-01-01" }],
    });
    (useApiModule.useBrokerBalance as jest.Mock).mockReturnValue({
      data: { available: 10000, total: 10000 },
    });
  });

  it("renders spot/futures toggle", () => {
    render(<ChakraProvider><OrderForm symbol="BTCUSDT" currentPrice={83000} /></ChakraProvider>);
    expect(screen.getByText("Spot")).toBeInTheDocument();
    expect(screen.getByText("Futures")).toBeInTheDocument();
  });

  it("renders buy/sell buttons", () => {
    render(<ChakraProvider><OrderForm symbol="BTCUSDT" currentPrice={83000} /></ChakraProvider>);
    expect(screen.getByText("Buy")).toBeInTheDocument();
    expect(screen.getByText("Sell")).toBeInTheDocument();
  });

  it("shows broker selector", () => {
    render(<ChakraProvider><OrderForm symbol="BTCUSDT" currentPrice={83000} /></ChakraProvider>);
    expect(screen.getByText(/Select broker/)).toBeInTheDocument();
  });

  it("disables submit when no broker selected", () => {
    render(<ChakraProvider><OrderForm symbol="BTCUSDT" currentPrice={83000} /></ChakraProvider>);
    const submitBtn = screen.getByRole("button", { name: /Buy BTCUSDT/i });
    expect(submitBtn).toBeDisabled();
  });
});
