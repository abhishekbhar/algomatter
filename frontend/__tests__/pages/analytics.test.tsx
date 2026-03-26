import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import AnalyticsPage from "@/app/(dashboard)/analytics/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/components/charts/EquityCurve", () => ({ EquityCurve: () => <div data-testid="equity-curve" /> }));
jest.mock("@/components/charts/ChartContainer", () => ({ ChartContainer: ({ children }: any) => <div>{children("1M")}</div> }));
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("AnalyticsPage", () => {
  it("renders portfolio stat cards", () => {
    (useApiModule.useAnalyticsOverview as jest.Mock).mockReturnValue({
      data: { total_pnl: 25000, active_strategies: 5, open_positions: 3, trades_today: 8 }, isLoading: false,
    });
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [{ id: "1", name: "NIFTY", mode: "paper", is_active: true }], isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><AnalyticsPage /></ChakraProvider>);
    expect(screen.getByText("Portfolio Overview")).toBeInTheDocument();
    expect(screen.getByText("Active Strategies")).toBeInTheDocument();
  });
});
