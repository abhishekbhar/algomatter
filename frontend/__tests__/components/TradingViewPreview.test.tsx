import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { TradingViewPreview } from "@/components/strategies/TradingViewPreview";

jest.mock("@chakra-ui/react", () => ({
  ...jest.requireActual("@chakra-ui/react"),
  useClipboard: () => ({ hasCopied: false, onCopy: jest.fn() }),
}));

const wrap = (ui: React.ReactElement) =>
  render(<ChakraProvider>{ui}</ChakraProvider>);

describe("TradingViewPreview", () => {
  it("shows only signal fields in the TradingView JSON", () => {
    const mapping = {
      exchange: "EXCHANGE1",
      product_type: "FUTURES",
      symbol: "BTCUSDT",          // fixed — plain string
      action: "$.action",          // signal — JSONPath
      quantity: "$.qty",           // signal — JSONPath
      leverage: 10,                // fixed — number
    };
    wrap(<TradingViewPreview mappingTemplate={mapping} />);
    const preview = screen.getByTestId("tv-json-preview");
    const json = JSON.parse(preview.textContent!);
    // Only signal fields ($.xxx) should appear
    expect(json).toEqual({
      action: "{{action}}",
      qty: "{{qty}}",
    });
    // Fixed fields must NOT appear
    expect(json).not.toHaveProperty("symbol");
    expect(json).not.toHaveProperty("leverage");
    expect(json).not.toHaveProperty("exchange");
  });

  it("uses the signal field name (after $.) as both key and template placeholder", () => {
    const mapping = { quantity: "$.qty" };
    wrap(<TradingViewPreview mappingTemplate={mapping} />);
    const json = JSON.parse(screen.getByTestId("tv-json-preview").textContent!);
    // key = "qty" (after $.), value = "{{qty}}"
    expect(json.qty).toBe("{{qty}}");
    expect(json).not.toHaveProperty("quantity");
  });

  it("shows webhook URL and Copy button when webhookUrl is provided", () => {
    wrap(
      <TradingViewPreview
        mappingTemplate={{}}
        webhookUrl="https://algomatter.in/api/v1/webhook/abc123"
      />
    );
    expect(
      screen.getByText("https://algomatter.in/api/v1/webhook/abc123")
    ).toBeInTheDocument();
    // Two copy buttons: one for URL, one for JSON
    expect(screen.getAllByRole("button", { name: /copy/i })).toHaveLength(2);
  });

  it("hides webhook URL section when webhookUrl is not provided", () => {
    wrap(<TradingViewPreview mappingTemplate={{}} />);
    expect(screen.queryByText(/webhook url/i)).not.toBeInTheDocument();
    // Only one copy button (for JSON)
    expect(screen.getAllByRole("button", { name: /copy/i })).toHaveLength(1);
  });

  it("shows empty JSON object when all fields are fixed", () => {
    const mapping = { symbol: "BTCUSDT", leverage: 10, exchange: "EXCHANGE1" };
    wrap(<TradingViewPreview mappingTemplate={mapping} />);
    const json = JSON.parse(screen.getByTestId("tv-json-preview").textContent!);
    expect(json).toEqual({});
  });

  it("shows how-to instructions", () => {
    wrap(<TradingViewPreview mappingTemplate={{}} />);
    // "How to use in TradingView" heading is always rendered (not conditional on webhookUrl)
    expect(screen.getByText(/how to use in tradingview/i)).toBeInTheDocument();
  });
});
