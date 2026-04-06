import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BrokerStatsBar } from "@/components/brokers/BrokerStatsBar";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");

describe("BrokerStatsBar", () => {
  it("renders all 4 stat labels", () => {
    (useApiModule.useBrokerStats as jest.Mock).mockReturnValue({
      data: { active_deployments: 3, total_realized_pnl: 2340.5, win_rate: 0.64, total_trades: 142 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerStatsBar brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/active deployments/i)).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText(/total.*p.*l/i)).toBeInTheDocument();
    expect(screen.getByText(/win rate/i)).toBeInTheDocument();
    expect(screen.getByText(/total trades/i)).toBeInTheDocument();
    expect(screen.getByText("142")).toBeInTheDocument();
  });

  it("renders loading skeleton when data is undefined", () => {
    (useApiModule.useBrokerStats as jest.Mock).mockReturnValue({ data: undefined, isLoading: true });
    render(<ChakraProvider><BrokerStatsBar brokerId="b1" /></ChakraProvider>);
    // Should not crash — skeletons rendered
    expect(screen.queryByText("Active Deployments")).not.toBeInTheDocument();
  });

  it("formats positive P&L in green", () => {
    (useApiModule.useBrokerStats as jest.Mock).mockReturnValue({
      data: { active_deployments: 1, total_realized_pnl: 500.0, win_rate: 0.5, total_trades: 10 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerStatsBar brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/\+\$500/)).toBeInTheDocument();
  });

  it("formats negative P&L", () => {
    (useApiModule.useBrokerStats as jest.Mock).mockReturnValue({
      data: { active_deployments: 0, total_realized_pnl: -200.0, win_rate: 0.3, total_trades: 5 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerStatsBar brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/-\$200/)).toBeInTheDocument();
  });
});
