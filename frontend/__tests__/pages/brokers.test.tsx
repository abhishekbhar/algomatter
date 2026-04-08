import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import BrokersPage from "@/app/(dashboard)/brokers/page";
import * as useApiModule from "@/lib/hooks/useApi";
import * as clientModule from "@/lib/api/client";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));
jest.mock("@/lib/api/client", () => {
  const actual = jest.requireActual("@/lib/api/client");
  return { ...actual, apiClient: jest.fn() };
});

const mockApiClient = clientModule.apiClient as jest.Mock;

describe("BrokersPage", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  it("renders broker cards with label as title and broker_type as subtitle", () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{
        id: "1",
        broker_type: "zerodha",
        label: "Main Account",
        is_active: true,
        connected_at: "2026-01-01",
      }],
      isLoading: false,
      mutate: jest.fn(),
    });
    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    expect(screen.getByText("Main Account")).toBeInTheDocument();
    expect(screen.getByText(/zerodha/i)).toBeInTheDocument(); // subtitle
    expect(screen.getByText("Add Broker")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [], isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    expect(screen.getByText(/no broker/i)).toBeInTheDocument();
  });

  it("broker card links to detail page", () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{
        id: "broker-123",
        broker_type: "exchange1",
        label: "Ex1 Main",
        is_active: true,
        connected_at: "2026-01-01",
      }],
      isLoading: false,
      mutate: jest.fn(),
    });
    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    const link = screen.getByRole("link", { name: /Ex1 Main/i });
    expect(link).toHaveAttribute("href", "/brokers/broker-123");
  });

  it("edit button opens rename modal and saving calls PATCH + mutate", async () => {
    const mutate = jest.fn();
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{
        id: "broker-abc",
        broker_type: "exchange1",
        label: "Old Label",
        is_active: true,
        connected_at: "2026-01-01",
      }],
      isLoading: false,
      mutate,
    });
    mockApiClient.mockResolvedValueOnce({});

    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    fireEvent.click(screen.getByLabelText(/rename/i));
    const input = screen.getByDisplayValue("Old Label");
    fireEvent.change(input, { target: { value: "New Label" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(mockApiClient).toHaveBeenCalledWith(
        "/api/v1/brokers/broker-abc",
        expect.objectContaining({ method: "PATCH", body: { label: "New Label" } }),
      ),
    );
    await waitFor(() => expect(mutate).toHaveBeenCalled());
  });

  it("keeps modal open with inline error on 409", async () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{
        id: "broker-xyz",
        broker_type: "exchange1",
        label: "Old",
        is_active: true,
        connected_at: "2026-01-01",
      }],
      isLoading: false,
      mutate: jest.fn(),
    });
    mockApiClient.mockRejectedValueOnce(
      new clientModule.ApiError(409, {
        detail: "A broker connection with this label already exists",
      }),
    );

    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    fireEvent.click(screen.getByLabelText(/rename/i));
    fireEvent.change(screen.getByDisplayValue("Old"), { target: { value: "Taken" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(screen.getByText(/already exists/i)).toBeInTheDocument(),
    );
    // Modal remains mounted — save button still visible
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
  });
});
