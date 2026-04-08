import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import BrokerDetailPage from "@/app/(dashboard)/brokers/[id]/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  useParams: () => ({ id: "broker-abc" }),
}));
jest.mock("@/components/brokers/BrokerStatsBar", () => ({
  BrokerStatsBar: () => <div data-testid="stats-bar" />,
}));
jest.mock("@/components/brokers/BrokerPositionsTable", () => ({
  BrokerPositionsTable: () => <div data-testid="positions-table" />,
}));
jest.mock("@/components/brokers/BrokerOrdersTable", () => ({
  BrokerOrdersTable: () => <div data-testid="orders-table" />,
}));
jest.mock("@/components/brokers/BrokerTradesTable", () => ({
  BrokerTradesTable: () => <div data-testid="trades-table" />,
}));

describe("BrokerDetailPage", () => {
  beforeEach(() => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{
        id: "broker-abc",
        broker_type: "exchange1",
        label: "Main Ex1",
        is_active: true,
        connected_at: "2026-01-01",
      }],
      isLoading: false,
    });
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({ data: [], isLoading: false });
    (useApiModule.useBrokerOrders as jest.Mock).mockReturnValue({ data: [], isLoading: false });
  });

  it("renders broker label in heading", () => {
    render(<ChakraProvider><BrokerDetailPage /></ChakraProvider>);
    expect(screen.getByRole("heading", { name: "Main Ex1" })).toBeInTheDocument();
  });

  it("renders stats bar", () => {
    render(<ChakraProvider><BrokerDetailPage /></ChakraProvider>);
    expect(screen.getByTestId("stats-bar")).toBeInTheDocument();
  });

  it("renders tab labels", () => {
    render(<ChakraProvider><BrokerDetailPage /></ChakraProvider>);
    expect(screen.getByRole("tab", { name: /positions/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /open orders/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /order history/i })).toBeInTheDocument();
  });

  it("renders back link to /brokers", () => {
    render(<ChakraProvider><BrokerDetailPage /></ChakraProvider>);
    expect(screen.getByRole("link", { name: /brokers/i })).toHaveAttribute("href", "/brokers");
  });
});
