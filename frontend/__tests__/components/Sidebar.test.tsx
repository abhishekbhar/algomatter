import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { Sidebar } from "@/components/layout/Sidebar";

jest.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: jest.fn() }),
}));

const wrap = (ui: React.ReactElement) =>
  render(<ChakraProvider>{ui}</ChakraProvider>);

describe("Sidebar", () => {
  it("renders all nav items", () => {
    wrap(<Sidebar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Strategies")).toBeInTheDocument();
    expect(screen.getByText("Webhooks")).toBeInTheDocument();
    expect(screen.getByText("Brokers")).toBeInTheDocument();
    expect(screen.getByText("Paper Trading")).toBeInTheDocument();
    expect(screen.getByText("Backtesting")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders Backtest Deployments nav item", () => {
    wrap(<Sidebar />);
    expect(screen.getByText("Backtest Deployments")).toBeInTheDocument();
  });
});
