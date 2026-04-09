import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { UpdateCredentialsModal } from "@/components/brokers/UpdateCredentialsModal";
import * as clientModule from "@/lib/api/client";

jest.mock("@/lib/api/client", () => {
  const actual = jest.requireActual("@/lib/api/client");
  return { ...actual, apiClient: jest.fn() };
});

const mockApiClient = clientModule.apiClient as jest.Mock;

function setup(overrides: Partial<React.ComponentProps<typeof UpdateCredentialsModal>> = {}) {
  const onClose = jest.fn();
  const onUpdated = jest.fn();
  render(
    <ChakraProvider>
      <UpdateCredentialsModal
        isOpen
        onClose={onClose}
        onUpdated={onUpdated}
        connectionId="conn-123"
        brokerType="exchange1"
        {...overrides}
      />
    </ChakraProvider>,
  );
  return { onClose, onUpdated };
}

describe("UpdateCredentialsModal", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  it("renders credential fields for the broker type", () => {
    setup();
    expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/private key/i)).toBeInTheDocument();
  });

  it("Update button is disabled when fields are empty", () => {
    setup();
    expect(screen.getByRole("button", { name: /update/i })).toBeDisabled();
  });

  it("calls PATCH with credentials and invokes onUpdated on success", async () => {
    mockApiClient.mockResolvedValueOnce({});
    const { onUpdated } = setup();

    fireEvent.change(screen.getByLabelText(/api key/i), { target: { value: "new-key" } });
    fireEvent.change(screen.getByLabelText(/private key/i), { target: { value: "new-private" } });
    fireEvent.click(screen.getByRole("button", { name: /update/i }));

    await waitFor(() => expect(mockApiClient).toHaveBeenCalledTimes(1));
    expect(mockApiClient).toHaveBeenCalledWith(
      "/api/v1/brokers/conn-123",
      expect.objectContaining({
        method: "PATCH",
        body: { credentials: { api_key: "new-key", private_key: "new-private" } },
      }),
    );
    await waitFor(() => expect(onUpdated).toHaveBeenCalledTimes(1));
  });

  it("shows error message and stays open on failure", async () => {
    mockApiClient.mockRejectedValueOnce(new Error("Server error"));
    const { onClose } = setup();

    fireEvent.change(screen.getByLabelText(/api key/i), { target: { value: "k" } });
    fireEvent.change(screen.getByLabelText(/private key/i), { target: { value: "p" } });
    fireEvent.click(screen.getByRole("button", { name: /update/i }));

    await waitFor(() =>
      expect(screen.getByText(/failed to update credentials/i)).toBeInTheDocument(),
    );
    expect(onClose).not.toHaveBeenCalled();
  });

  it("renders zerodha fields when brokerType is zerodha", () => {
    setup({ brokerType: "zerodha" });
    expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/api secret/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/user id/i)).toBeInTheDocument();
  });
});
