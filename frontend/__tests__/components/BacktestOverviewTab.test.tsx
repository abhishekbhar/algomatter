import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BacktestOverviewTab } from "@/components/backtest-deployments/BacktestOverviewTab";
import type { DeploymentResult } from "@/lib/api/types";

const result: DeploymentResult = {
  id: "res-1",
  deployment_id: "dep-1",
  trade_log: null,
  equity_curve: [
    { timestamp: "2024-04-03T10:00:00Z", equity: 100000 },
    { timestamp: "2024-04-03T11:00:00Z", equity: 118400 },
  ],
  metrics: {
    total_return: 18.4,
    win_rate: 64,
    profit_factor: 2.1,
    sharpe_ratio: 1.8,
    max_drawdown: -7.2,
    total_trades: 42,
    avg_trade_pnl: 438,
  },
  status: "completed",
  created_at: "2024-04-03T10:00:00Z",
  completed_at: "2024-04-03T11:00:00Z",
};

const wrap = (ui: React.ReactElement) => render(<ChakraProvider>{ui}</ChakraProvider>);

describe("BacktestOverviewTab", () => {
  it("shows in-progress placeholder when status is running", () => {
    wrap(<BacktestOverviewTab result={null} deploymentStatus="running" />);
    expect(screen.getByText(/in progress/i)).toBeInTheDocument();
  });

  it("shows queued placeholder when status is pending", () => {
    wrap(<BacktestOverviewTab result={null} deploymentStatus="pending" />);
    expect(screen.getByText(/queued/i)).toBeInTheDocument();
  });

  it("renders metrics when result is provided", () => {
    wrap(<BacktestOverviewTab result={result} deploymentStatus="completed" />);
    expect(screen.getByText(/profit factor/i)).toBeInTheDocument();
    expect(screen.getByText("2.10")).toBeInTheDocument();
    expect(screen.getByText(/avg trade/i)).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
