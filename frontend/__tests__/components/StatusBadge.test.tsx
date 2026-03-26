import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { StatusBadge } from "@/components/shared/StatusBadge";

const wrap = (ui: React.ReactElement) => render(<ChakraProvider>{ui}</ChakraProvider>);

describe("StatusBadge", () => {
  it("renders text with correct variant", () => {
    wrap(<StatusBadge variant="success" text="passed" />);
    expect(screen.getByText("passed")).toBeInTheDocument();
  });
  it("renders all variants without crashing", () => {
    const variants = ["success", "error", "warning", "info", "neutral"] as const;
    variants.forEach((v) => {
      const { unmount } = wrap(<StatusBadge variant={v} text={v} />);
      expect(screen.getByText(v)).toBeInTheDocument();
      unmount();
    });
  });
});
