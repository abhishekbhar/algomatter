import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import PaperTradingPage from "@/app/(dashboard)/paper-trading/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("PaperTradingPage", () => {
  it("renders sessions table", () => {
    (useApiModule.usePaperSessions as jest.Mock).mockReturnValue({
      data: [{ id: "1", strategy_id: "s1", initial_capital: "100000", current_balance: "105000", status: "active", started_at: "2026-01-01T00:00:00Z" }],
      isLoading: false, mutate: jest.fn(),
    });
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [{ id: "s1", name: "Test Strategy" }], isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><PaperTradingPage /></ChakraProvider>);
    expect(screen.getByText("Start Session")).toBeInTheDocument();
  });
  it("renders empty state", () => {
    (useApiModule.usePaperSessions as jest.Mock).mockReturnValue({ data: [], isLoading: false, mutate: jest.fn() });
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({ data: [], isLoading: false, mutate: jest.fn() });
    render(<ChakraProvider><PaperTradingPage /></ChakraProvider>);
    expect(screen.getByText(/no paper trading/i)).toBeInTheDocument();
  });
});
