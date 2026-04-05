import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { WebhookParameterBuilder } from "@/components/strategies/WebhookParameterBuilder";

// Mock SymbolSelect — not testing the instrument dropdown here
jest.mock("@/components/shared/SymbolSelect", () => ({
  SymbolSelect: ({ value, onChange }: { value: string; onChange: (s: string) => void }) => (
    <input
      data-testid="symbol-select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

const wrap = (ui: React.ReactElement) =>
  render(<ChakraProvider>{ui}</ChakraProvider>);

describe("WebhookParameterBuilder", () => {
  it("calls onChange on mount with a valid futures mapping_template", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall.exchange).toBe("EXCHANGE1");
    expect(lastCall.product_type).toBe("FUTURES");
    expect(lastCall.action).toBe("$.action");
    expect(lastCall.symbol).toBe("BTCUSDT");
    expect(lastCall.leverage).toBe(10);
  });

  it("emits DELIVERY product_type when Spot tab is selected", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    fireEvent.click(screen.getByRole("tab", { name: "Spot" }));
    await waitFor(() => {
      const calls = onChange.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall.product_type).toBe("DELIVERY");
    });
  });

  it("emits fixed value (not JSONPath) when source is Fixed", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall.order_type).toBe("MARKET");
    expect(String(lastCall.order_type).startsWith("$.")).toBe(false);
  });

  it("emits JSONPath when source is toggled to From signal", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("order_type-signal-btn"));
    await waitFor(() => {
      const calls = onChange.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall.order_type).toBe("$.order_type");
    });
  });

  it("does not include optional fields when show optional is collapsed", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall).not.toHaveProperty("price");
    expect(lastCall).not.toHaveProperty("take_profit");
    expect(lastCall).not.toHaveProperty("stop_loss");
  });

  it("includes optional fields after expanding optional section", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /show optional/i }));
    fireEvent.change(screen.getByTestId("price-signal-input"), {
      target: { value: "close" },
    });
    await waitFor(() => {
      const calls = onChange.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall.price).toBe("$.close");
    });
  });

  it("emits leverage as a JS number, not a string", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(typeof lastCall.leverage).toBe("number");
  });
});
