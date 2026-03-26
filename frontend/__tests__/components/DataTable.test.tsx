import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChakraProvider } from "@chakra-ui/react";
import { DataTable, Column } from "@/components/shared/DataTable";

const wrap = (ui: React.ReactElement) => render(<ChakraProvider>{ui}</ChakraProvider>);

interface Row { id: string; name: string; value: number; }

const columns: Column<Row>[] = [
  { key: "name", header: "Name" },
  { key: "value", header: "Value", sortable: true },
];

const data: Row[] = [
  { id: "1", name: "Alpha", value: 100 },
  { id: "2", name: "Beta", value: 50 },
  { id: "3", name: "Gamma", value: 200 },
];

describe("DataTable", () => {
  it("renders headers and rows", () => {
    wrap(<DataTable columns={columns} data={data} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
  });

  it("sorts by sortable column on click", async () => {
    wrap(<DataTable columns={columns} data={data} />);
    const header = screen.getByText("Value");
    await userEvent.click(header);
    const cells = screen.getAllByRole("cell");
    const valuesCells = cells.filter((_, i) => i % 2 === 1);
    expect(valuesCells[0].textContent).toBe("50");
  });

  it("renders empty state when no data", () => {
    wrap(<DataTable columns={columns} data={[]} emptyMessage="No items" />);
    expect(screen.getByText("No items")).toBeInTheDocument();
  });
});
