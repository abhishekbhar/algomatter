import { render, screen, fireEvent } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { Watchlist } from "@/components/trade/Watchlist";

jest.mock("@/lib/hooks/useBinanceWebSocket", () => ({
  useBinanceTickerStream: jest.fn(() => ({ connected: true })),
}));

const wrap = (ui: React.ReactElement) =>
  render(<ChakraProvider>{ui}</ChakraProvider>);

describe("Watchlist", () => {
  it("renders default symbols", () => {
    wrap(
      <Watchlist activeSymbol="BTCUSDT" onSymbolSelect={jest.fn()} />,
    );
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("ETHUSDT")).toBeInTheDocument();
    expect(screen.getByText("SOLUSDT")).toBeInTheDocument();
  });

  it("filters symbols by search input", () => {
    wrap(
      <Watchlist activeSymbol="BTCUSDT" onSymbolSelect={jest.fn()} />,
    );

    const searchInput = screen.getByPlaceholderText("Search...");
    fireEvent.change(searchInput, { target: { value: "BTC" } });

    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.queryByText("ETHUSDT")).not.toBeInTheDocument();
  });

  it("calls onSymbolSelect when symbol clicked", () => {
    const onSelect = jest.fn();
    wrap(
      <Watchlist activeSymbol="BTCUSDT" onSymbolSelect={onSelect} />,
    );

    // Click on the ETH row — the short name "ETH" text
    fireEvent.click(screen.getByText("ETH"));
    expect(onSelect).toHaveBeenCalledWith("ETHUSDT");
  });
});
