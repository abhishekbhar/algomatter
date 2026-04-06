import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BrokerPositionsTable } from "@/components/brokers/BrokerPositionsTable";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/lib/api/client", () => ({ apiClient: jest.fn() }));

const mockPosition = {
  deployment_id: "dep-1",
  deployment_name: "BTC Strategy",
  symbol: "BTCUSDT",
  side: "LONG" as const,
  quantity: 0.05,
  avg_entry_price: 83200,
  unrealized_pnl: 124.5,
};

describe("BrokerPositionsTable", () => {
  it("renders position row", () => {
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({
      data: [mockPosition], isLoading: false,
    });
    render(<ChakraProvider><BrokerPositionsTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("LONG")).toBeInTheDocument();
    expect(screen.getByText("BTC Strategy")).toBeInTheDocument();
    expect(screen.getByText(/\+₹124/)).toBeInTheDocument();
  });

  it("renders empty state when no positions", () => {
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({ data: [], isLoading: false });
    render(<ChakraProvider><BrokerPositionsTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/no open positions/i)).toBeInTheDocument();
  });

  it("renders Close button per row", () => {
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({
      data: [mockPosition], isLoading: false,
    });
    render(<ChakraProvider><BrokerPositionsTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByRole("button", { name: /close/i })).toBeInTheDocument();
  });

  it("renders SHORT side in red", () => {
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({
      data: [{ ...mockPosition, side: "SHORT" as const, unrealized_pnl: -18 }],
      isLoading: false,
    });
    render(<ChakraProvider><BrokerPositionsTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText("SHORT")).toBeInTheDocument();
    expect(screen.getByText(/-₹18/)).toBeInTheDocument();
  });
});
