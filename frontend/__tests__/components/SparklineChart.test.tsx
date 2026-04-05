import { render } from "@testing-library/react";
import { SparklineChart } from "@/components/backtest-deployments/SparklineChart";

const points = [
  { timestamp: "2024-01-01T00:00:00Z", equity: 100000 },
  { timestamp: "2024-01-02T00:00:00Z", equity: 102000 },
  { timestamp: "2024-01-03T00:00:00Z", equity: 101000 },
  { timestamp: "2024-01-04T00:00:00Z", equity: 105000 },
];

describe("SparklineChart", () => {
  it("renders an SVG element", () => {
    const { container } = render(<SparklineChart data={points} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders a flat line when data is empty", () => {
    const { container } = render(<SparklineChart data={[]} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.querySelector("path, line")).toBeInTheDocument();
  });

  it("renders a flat line when data is null", () => {
    const { container } = render(<SparklineChart data={null} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders with custom width and height", () => {
    const { container } = render(<SparklineChart data={points} width={150} height={40} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "150");
    expect(svg).toHaveAttribute("height", "40");
  });
});
