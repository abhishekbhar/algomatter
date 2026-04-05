import { render, screen, fireEvent } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { ParameterRow } from "@/components/strategies/ParameterRow";

const wrap = (ui: React.ReactElement) =>
  render(<ChakraProvider>{ui}</ChakraProvider>);

const baseProps = {
  label: "Action",
  fieldKey: "action",
  required: true,
  source: "signal" as const,
  fixedValue: "BUY",
  signalField: "action",
  inputType: "select" as const,
  selectOptions: [
    { value: "BUY", label: "BUY" },
    { value: "SELL", label: "SELL" },
  ],
  onSourceChange: jest.fn(),
  onFixedChange: jest.fn(),
  onSignalFieldChange: jest.fn(),
};

describe("ParameterRow", () => {
  beforeEach(() => jest.clearAllMocks());

  it("renders the label", () => {
    wrap(<ParameterRow {...baseProps} />);
    expect(screen.getByText("Action")).toBeInTheDocument();
  });

  it("renders signal input when source is signal", () => {
    wrap(<ParameterRow {...baseProps} source="signal" />);
    expect(screen.getByTestId("action-signal-input")).toBeInTheDocument();
    expect(screen.queryByTestId("action-select")).not.toBeInTheDocument();
  });

  it("renders select when source is fixed and inputType is select", () => {
    wrap(<ParameterRow {...baseProps} source="fixed" />);
    expect(screen.getByTestId("action-select")).toBeInTheDocument();
    expect(screen.queryByTestId("action-signal-input")).not.toBeInTheDocument();
  });

  it("calls onSourceChange with 'fixed' when Fixed button clicked", () => {
    wrap(<ParameterRow {...baseProps} source="signal" />);
    fireEvent.click(screen.getByTestId("action-fixed-btn"));
    expect(baseProps.onSourceChange).toHaveBeenCalledWith("fixed");
  });

  it("calls onSourceChange with 'signal' when From signal button clicked", () => {
    wrap(<ParameterRow {...baseProps} source="fixed" />);
    fireEvent.click(screen.getByTestId("action-signal-btn"));
    expect(baseProps.onSourceChange).toHaveBeenCalledWith("signal");
  });

  it("calls onSignalFieldChange when signal input changes", () => {
    wrap(<ParameterRow {...baseProps} source="signal" signalField="" />);
    fireEvent.change(screen.getByTestId("action-signal-input"), {
      target: { value: "direction" },
    });
    expect(baseProps.onSignalFieldChange).toHaveBeenCalledWith("direction");
  });

  it("shows price error helper text when showPriceError is true and source is signal", () => {
    wrap(
      <ParameterRow
        {...baseProps}
        fieldKey="price"
        label="Price"
        source="signal"
        signalField=""
        inputType="number"
        showPriceError
      />
    );
    expect(
      screen.getByText(/required when order type is limit/i)
    ).toBeInTheDocument();
  });

  it("renders NumberInput when inputType is number and source is fixed", () => {
    wrap(
      <ParameterRow
        {...baseProps}
        fieldKey="quantity"
        label="Quantity"
        source="fixed"
        fixedValue={5}
        inputType="number"
      />
    );
    expect(screen.getByTestId("quantity-number-input")).toBeInTheDocument();
  });

  it("renders custom fixed input when provided and source is fixed", () => {
    wrap(
      <ParameterRow
        {...baseProps}
        source="fixed"
        customFixedInput={<div data-testid="custom-input">Custom</div>}
      />
    );
    expect(screen.getByTestId("custom-input")).toBeInTheDocument();
  });

  it("calls onFixedChange when select value changes", () => {
    wrap(<ParameterRow {...baseProps} source="fixed" />);
    fireEvent.change(screen.getByTestId("action-select"), {
      target: { value: "SELL" },
    });
    expect(baseProps.onFixedChange).toHaveBeenCalledWith("SELL");
  });
});
