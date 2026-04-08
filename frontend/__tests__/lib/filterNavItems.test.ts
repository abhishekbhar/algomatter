import { filterNavItems, NavItemDescriptor } from "@/lib/utils/filterNavItems";

const ITEMS: NavItemDescriptor[] = [
  { label: "Dashboard", href: "/" },
  { label: "Paper Trading", href: "/paper-trading" },
  { label: "Backtest Deployments", href: "/backtest-deployments" },
  { label: "Backtesting", href: "/backtesting" },
  { label: "Analytics", href: "/analytics" },
];

describe("filterNavItems", () => {
  it("returns all items when both flags are on", () => {
    const result = filterNavItems(ITEMS, {
      paperTrading: true,
      backtesting: true,
    });
    expect(result).toHaveLength(5);
    expect(result.map((i) => i.href)).toEqual([
      "/",
      "/paper-trading",
      "/backtest-deployments",
      "/backtesting",
      "/analytics",
    ]);
  });

  it("hides Paper Trading when paperTrading flag is off", () => {
    const result = filterNavItems(ITEMS, {
      paperTrading: false,
      backtesting: true,
    });
    expect(result.map((i) => i.href)).toEqual([
      "/",
      "/backtest-deployments",
      "/backtesting",
      "/analytics",
    ]);
  });

  it("hides Backtest Deployments and Backtesting when backtesting flag is off", () => {
    const result = filterNavItems(ITEMS, {
      paperTrading: true,
      backtesting: false,
    });
    expect(result.map((i) => i.href)).toEqual([
      "/",
      "/paper-trading",
      "/analytics",
    ]);
  });

  it("hides all three when both flags are off", () => {
    const result = filterNavItems(ITEMS, {
      paperTrading: false,
      backtesting: false,
    });
    expect(result.map((i) => i.href)).toEqual(["/", "/analytics"]);
  });

  it("does not mutate the input array", () => {
    const input = [...ITEMS];
    filterNavItems(input, { paperTrading: false, backtesting: false });
    expect(input).toHaveLength(5);
  });
});
