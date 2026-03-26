import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import StrategiesPage from "@/app/(dashboard)/strategies/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("StrategiesPage", () => {
  it("renders strategies table with data", () => {
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [{ id: "1", name: "NIFTY Momentum", mode: "paper", is_active: true, created_at: "2026-01-01" }],
      isLoading: false, error: undefined, mutate: jest.fn(),
    });
    render(<ChakraProvider><StrategiesPage /></ChakraProvider>);
    expect(screen.getByText("NIFTY Momentum")).toBeInTheDocument();
    expect(screen.getByText("New Strategy")).toBeInTheDocument();
  });
  it("renders empty state when no strategies", () => {
    (useApiModule.useStrategies as jest.Mock).mockReturnValue({
      data: [], isLoading: false, error: undefined, mutate: jest.fn(),
    });
    render(<ChakraProvider><StrategiesPage /></ChakraProvider>);
    expect(screen.getByText(/no strategies/i)).toBeInTheDocument();
  });
});
