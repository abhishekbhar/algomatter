import { render, screen, waitFor } from "@testing-library/react";
import {
  FeatureFlagsProvider,
  useFeatureFlags,
} from "@/lib/contexts/FeatureFlagsContext";

function Probe() {
  const { paperTrading, backtesting, isLoading } = useFeatureFlags();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="paper">{String(paperTrading)}</span>
      <span data-testid="backtesting">{String(backtesting)}</span>
    </div>
  );
}

describe("FeatureFlagsProvider", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("exposes flags after successful fetch", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        featureFlags: { paperTrading: false, backtesting: false },
      }),
    }) as unknown as typeof fetch;

    render(
      <FeatureFlagsProvider>
        <Probe />
      </FeatureFlagsProvider>,
    );

    // While loading, defaults are true
    expect(screen.getByTestId("loading").textContent).toBe("true");

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    expect(screen.getByTestId("paper").textContent).toBe("false");
    expect(screen.getByTestId("backtesting").textContent).toBe("false");
  });

  it("fails open (defaults to both true) on fetch error", async () => {
    global.fetch = jest
      .fn()
      .mockRejectedValue(new Error("network down")) as unknown as typeof fetch;

    render(
      <FeatureFlagsProvider>
        <Probe />
      </FeatureFlagsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    expect(screen.getByTestId("paper").textContent).toBe("true");
    expect(screen.getByTestId("backtesting").textContent).toBe("true");
  });

  it("fails open on non-ok HTTP response", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    }) as unknown as typeof fetch;

    render(
      <FeatureFlagsProvider>
        <Probe />
      </FeatureFlagsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    expect(screen.getByTestId("paper").textContent).toBe("true");
    expect(screen.getByTestId("backtesting").textContent).toBe("true");
  });

  it("fails open when payload is missing featureFlags key", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    }) as unknown as typeof fetch;

    render(
      <FeatureFlagsProvider>
        <Probe />
      </FeatureFlagsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    expect(screen.getByTestId("paper").textContent).toBe("true");
    expect(screen.getByTestId("backtesting").textContent).toBe("true");
  });

  it("fails open when featureFlags values are non-boolean", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        featureFlags: { paperTrading: "false", backtesting: null },
      }),
    }) as unknown as typeof fetch;

    render(
      <FeatureFlagsProvider>
        <Probe />
      </FeatureFlagsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    expect(screen.getByTestId("paper").textContent).toBe("true");
    expect(screen.getByTestId("backtesting").textContent).toBe("true");
  });
});
