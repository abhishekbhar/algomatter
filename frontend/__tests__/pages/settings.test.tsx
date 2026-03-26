import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import SettingsPage from "@/app/(dashboard)/settings/page";
import * as useApiModule from "@/lib/hooks/useApi";
import { AuthProvider } from "@/lib/hooks/useAuth";
import * as client from "@/lib/api/client";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/lib/api/client");

describe("SettingsPage", () => {
  it("renders health status and profile", () => {
    (useApiModule.useHealth as jest.Mock).mockReturnValue({ data: { status: "ok" }, isLoading: false });
    (useApiModule.useWebhookConfig as jest.Mock).mockReturnValue({ data: { webhook_url: "url", token: "tok" }, isLoading: false, mutate: jest.fn() });
    (client.getRefreshToken as jest.Mock).mockReturnValue(null);
    render(<ChakraProvider><AuthProvider><SettingsPage /></AuthProvider></ChakraProvider>);
    expect(screen.getByText(/system health/i)).toBeInTheDocument();
    expect(screen.getByText(/theme/i)).toBeInTheDocument();
  });
});
