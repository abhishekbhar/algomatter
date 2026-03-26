import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import DashboardPage from "@/app/(dashboard)/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/components/charts/EquityCurve", () => ({ EquityCurve: () => <div data-testid="equity-curve" /> }));
jest.mock("@/components/charts/ChartContainer", () => ({ ChartContainer: ({ children }: any) => <div>{children("1M")}</div> }));
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

const mockOverview = {
  data: { total_pnl: 12500, active_strategies: 3, open_positions: 5, trades_today: 12 },
  error: undefined, isLoading: false, mutate: jest.fn(), isValidating: false,
};

describe("DashboardPage", () => {
  beforeEach(() => {
    (useApiModule.useAnalyticsOverview as jest.Mock).mockReturnValue(mockOverview);
    (useApiModule.useWebhookSignals as jest.Mock).mockReturnValue({ data: [], error: undefined, isLoading: false, mutate: jest.fn(), isValidating: false });
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({ data: [], error: undefined, isLoading: false, mutate: jest.fn(), isValidating: false });
    (useApiModule.usePaperSessions as jest.Mock).mockReturnValue({ data: [], error: undefined, isLoading: false, mutate: jest.fn(), isValidating: false });
  });
  it("renders stat cards", () => {
    render(<ChakraProvider><DashboardPage /></ChakraProvider>);
    expect(screen.getByText("Active Strategies")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Today's Signals")).toBeInTheDocument();
  });
  it("renders quick action buttons", () => {
    render(<ChakraProvider><DashboardPage /></ChakraProvider>);
    expect(screen.getByText("New Strategy")).toBeInTheDocument();
    expect(screen.getByText("Run Backtest")).toBeInTheDocument();
    expect(screen.getByText("Connect Broker")).toBeInTheDocument();
  });
});
