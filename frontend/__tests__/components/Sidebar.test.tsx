import { render, screen, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { Sidebar } from "@/components/layout/Sidebar";
import { FeatureFlagsProvider } from "@/lib/contexts/FeatureFlagsContext";

jest.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: jest.fn() }),
}));

// Stub fetch so FeatureFlagsProvider resolves deterministically per test.
function mockFlagsFetch(flags: { paperTrading: boolean; backtesting: boolean }) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ featureFlags: flags }),
  }) as unknown as typeof fetch;
}

const wrap = (ui: React.ReactElement) =>
  render(
    <ChakraProvider>
      <FeatureFlagsProvider>{ui}</FeatureFlagsProvider>
    </ChakraProvider>,
  );

describe("Sidebar", () => {
  const originalFetch = global.fetch;
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders all nav items when all flags are on", async () => {
    mockFlagsFetch({ paperTrading: true, backtesting: true });
    wrap(<Sidebar />);
    // Non-flagged items always present
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Webhook Strategies")).toBeInTheDocument();
    expect(screen.getByText("Hosted Strategies")).toBeInTheDocument();
    expect(screen.getByText("Webhooks")).toBeInTheDocument();
    expect(screen.getByText("Brokers")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
    // Flagged items are visible under the fail-open default and remain so
    // once the provider resolves to {paperTrading: true, backtesting: true}.
    await waitFor(() => {
      expect(screen.getByText("Paper Trading")).toBeInTheDocument();
    });
    expect(screen.getByText("Backtest Deployments")).toBeInTheDocument();
    expect(screen.getByText("Backtesting")).toBeInTheDocument();
    // Guard against the test being tautological with the fail-open default:
    // confirm the provider actually fired its config fetch.
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/config"),
      );
    });
  });

  it("hides Paper Trading tab when paperTrading flag is off", async () => {
    mockFlagsFetch({ paperTrading: false, backtesting: true });
    wrap(<Sidebar />);
    // Wait for the provider to flip flags off by confirming Paper Trading disappears.
    await waitFor(() => {
      expect(screen.queryByText("Paper Trading")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Backtest Deployments")).toBeInTheDocument();
    expect(screen.getByText("Backtesting")).toBeInTheDocument();
  });

  it("hides Backtest Deployments and Backtesting when backtesting flag is off", async () => {
    mockFlagsFetch({ paperTrading: true, backtesting: false });
    wrap(<Sidebar />);
    await waitFor(() => {
      expect(screen.queryByText("Backtest Deployments")).not.toBeInTheDocument();
    });
    expect(screen.queryByText("Backtesting")).not.toBeInTheDocument();
    expect(screen.getByText("Paper Trading")).toBeInTheDocument();
  });

  it("hides all three flagged tabs when both flags are off", async () => {
    mockFlagsFetch({ paperTrading: false, backtesting: false });
    wrap(<Sidebar />);
    await waitFor(() => {
      expect(screen.queryByText("Paper Trading")).not.toBeInTheDocument();
    });
    expect(screen.queryByText("Backtest Deployments")).not.toBeInTheDocument();
    expect(screen.queryByText("Backtesting")).not.toBeInTheDocument();
    // Non-flagged items unaffected
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
  });
});
