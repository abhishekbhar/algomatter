import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { StatCard } from "@/components/shared/StatCard";

const wrap = (ui: React.ReactElement) => render(<ChakraProvider>{ui}</ChakraProvider>);

describe("StatCard", () => {
  it("renders label and value", () => {
    wrap(<StatCard label="Total P&L" value="₹12,500" />);
    expect(screen.getByText("Total P&L")).toBeInTheDocument();
    expect(screen.getByText("₹12,500")).toBeInTheDocument();
  });
  it("renders positive change indicator", () => {
    wrap(<StatCard label="Return" value="15%" change={5.2} />);
    expect(screen.getByText("+5.20%")).toBeInTheDocument();
  });
  it("renders negative change indicator", () => {
    wrap(<StatCard label="Return" value="-3%" change={-2.1} />);
    expect(screen.getByText("-2.10%")).toBeInTheDocument();
  });
});
