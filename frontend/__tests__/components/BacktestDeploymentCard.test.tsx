import { render, screen, fireEvent } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BacktestDeploymentCard } from "@/components/backtest-deployments/BacktestDeploymentCard";
import type { Deployment, DeploymentResult } from "@/lib/api/types";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const baseDeployment: Deployment = {
  id: "dep-1",
  strategy_name: "momentum_v2",
  strategy_code_id: "sc-1",
  strategy_code_version_id: "scv-1",
  mode: "backtest",
  status: "completed",
  symbol: "NIFTY50",
  exchange: "NSE",
  product_type: "MIS",
  interval: "15m",
  broker_connection_id: null,
  cron_expression: null,
  config: {},
  params: {},
  promoted_from_id: null,
  created_at: "2024-04-03T10:00:00Z",
  started_at: "2024-04-03T10:01:00Z",
  stopped_at: "2024-04-03T11:00:00Z",
};

const completedResult: DeploymentResult = {
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

describe("BacktestDeploymentCard", () => {
  it("renders strategy name and symbol", () => {
    wrap(<BacktestDeploymentCard deployment={baseDeployment} result={null} isPromoted={false} onPromote={jest.fn()} />);
    expect(screen.getByText("momentum_v2")).toBeInTheDocument();
    expect(screen.getByText(/NIFTY50/)).toBeInTheDocument();
  });

  it("shows metrics for completed deployment", () => {
    wrap(<BacktestDeploymentCard deployment={baseDeployment} result={completedResult} isPromoted={false} onPromote={jest.fn()} />);
    expect(screen.getByText(/18.4/)).toBeInTheDocument();
    expect(screen.getByText(/64/)).toBeInTheDocument();
  });

  it("shows Promote button when completed and not promoted", () => {
    wrap(<BacktestDeploymentCard deployment={baseDeployment} result={completedResult} isPromoted={false} onPromote={jest.fn()} />);
    expect(screen.getByRole("button", { name: /promote/i })).toBeInTheDocument();
  });

  it("hides Promote button when already promoted", () => {
    wrap(<BacktestDeploymentCard deployment={baseDeployment} result={completedResult} isPromoted={true} onPromote={jest.fn()} />);
    expect(screen.queryByRole("button", { name: /promote/i })).not.toBeInTheDocument();
    expect(screen.getByText(/promoted/i)).toBeInTheDocument();
  });

  it("shows View Logs text for failed deployment", () => {
    const failed = { ...baseDeployment, status: "failed" as const };
    wrap(<BacktestDeploymentCard deployment={failed} result={null} isPromoted={false} onPromote={jest.fn()} />);
    expect(screen.getByText(/view logs/i)).toBeInTheDocument();
  });

  it("shows dashes for metrics when running", () => {
    const running = { ...baseDeployment, status: "running" as const };
    wrap(<BacktestDeploymentCard deployment={running} result={null} isPromoted={false} onPromote={jest.fn()} />);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("navigates to detail page on card click", () => {
    mockPush.mockClear();
    wrap(<BacktestDeploymentCard deployment={baseDeployment} result={null} isPromoted={false} onPromote={jest.fn()} />);
    fireEvent.click(screen.getByText("momentum_v2"));
    expect(mockPush).toHaveBeenCalledWith("/backtest-deployments/dep-1");
  });

  it("shows skeleton when result is undefined for completed deployment", () => {
    const { container } = wrap(
      <BacktestDeploymentCard deployment={baseDeployment} result={undefined} isPromoted={false} onPromote={jest.fn()} />
    );
    // Chakra Skeleton renders with data-testid or aria attributes — check for the skeleton wrapper
    expect(container.querySelector('[aria-busy="true"], [data-loading]') ?? container.querySelector(".chakra-skeleton")).toBeTruthy();
  });
});
