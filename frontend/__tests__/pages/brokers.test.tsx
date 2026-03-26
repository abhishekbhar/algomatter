import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import BrokersPage from "@/app/(dashboard)/brokers/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("BrokersPage", () => {
  it("renders broker cards", () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{ id: "1", broker_type: "zerodha", is_active: true, connected_at: "2026-01-01" }],
      isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    expect(screen.getByText("zerodha")).toBeInTheDocument();
    expect(screen.getByText("Add Broker")).toBeInTheDocument();
  });
  it("renders empty state", () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({ data: [], isLoading: false, mutate: jest.fn() });
    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    expect(screen.getByText(/no broker/i)).toBeInTheDocument();
  });
});
