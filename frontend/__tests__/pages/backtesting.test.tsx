import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import BacktestingPage from "@/app/(dashboard)/backtesting/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/components/charts/EquityCurve", () => ({ EquityCurve: () => <div data-testid="equity-curve" /> }));
jest.mock("@/components/charts/DrawdownChart", () => ({ DrawdownChart: () => <div data-testid="drawdown" /> }));
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("BacktestingPage", () => {
  beforeEach(() => {
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({ data: [{ id: "s1", name: "Test" }], isLoading: false, mutate: jest.fn() });
    (useApiModule.useBacktests as jest.Mock).mockReturnValue({ data: [], isLoading: false, mutate: jest.fn() });
  });
  it("renders run backtest form", () => {
    render(<ChakraProvider><BacktestingPage /></ChakraProvider>);
    expect(screen.getAllByText("Run Backtest").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText(/strategy/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/initial capital/i)).toBeInTheDocument();
  });
});
