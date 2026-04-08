import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { RenameBrokerModal } from "@/components/brokers/RenameBrokerModal";
import * as clientModule from "@/lib/api/client";

jest.mock("@/lib/api/client", () => {
  const actual = jest.requireActual("@/lib/api/client");
  return { ...actual, apiClient: jest.fn() };
});

const mockApiClient = clientModule.apiClient as jest.Mock;

function setup(overrides: Partial<React.ComponentProps<typeof RenameBrokerModal>> = {}) {
  const onClose = jest.fn();
  const onRenamed = jest.fn();
  render(
    <ChakraProvider>
      <RenameBrokerModal
        isOpen
        onClose={onClose}
        onRenamed={onRenamed}
        connectionId="conn-123"
        currentLabel="Old"
        {...overrides}
      />
    </ChakraProvider>,
  );
  return { onClose, onRenamed };
}

describe("RenameBrokerModal", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  it("prefills the current label", () => {
    setup();
    expect(screen.getByDisplayValue("Old")).toBeInTheDocument();
  });

  it("calls PATCH with the new trimmed label and invokes onRenamed", async () => {
    mockApiClient.mockResolvedValueOnce({});
    const { onRenamed } = setup();
    const input = screen.getByLabelText(/label/i);
    fireEvent.change(input, { target: { value: "  New Name  " } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(mockApiClient).toHaveBeenCalledTimes(1));
    expect(mockApiClient).toHaveBeenCalledWith(
      "/api/v1/brokers/conn-123",
      expect.objectContaining({ method: "PATCH", body: { label: "New Name" } }),
    );
    await waitFor(() => expect(onRenamed).toHaveBeenCalledTimes(1));
  });

  it("shows a 409 inline error without closing", async () => {
    const err = new clientModule.ApiError(409, {
      detail: "A broker connection with this label already exists",
    });
    mockApiClient.mockRejectedValueOnce(err);
    const { onClose, onRenamed } = setup();
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: "Taken" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(screen.getByText(/already exists/i)).toBeInTheDocument(),
    );
    expect(onClose).not.toHaveBeenCalled();
    expect(onRenamed).not.toHaveBeenCalled();
  });

  it("disables save when label is blank", () => {
    setup({ currentLabel: "Old" });
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: "   " } });
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });
});
