import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import WebhooksPage from "@/app/(dashboard)/webhooks/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe("WebhooksPage", () => {
  it("renders webhook config section", () => {
    (useApiModule.useWebhookConfig as jest.Mock).mockReturnValue({
      data: { webhook_url: "http://localhost:8000/api/v1/webhook/abc123", token: "abc123" },
      isLoading: false, mutate: jest.fn(),
    });
    (useApiModule.useWebhookSignals as jest.Mock).mockReturnValue({ data: [], isLoading: false, mutate: jest.fn() });
    render(<ChakraProvider><WebhooksPage /></ChakraProvider>);
    expect(screen.getByText(/webhook url/i)).toBeInTheDocument();
    expect(screen.getByText(/regenerate/i)).toBeInTheDocument();
  });
});
