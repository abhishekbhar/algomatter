import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import LoginPage from "@/app/(auth)/login/page";
import { AuthProvider } from "@/lib/hooks/useAuth";
import * as client from "@/lib/api/client";

jest.mock("@/lib/api/client");
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  redirect: jest.fn(),
}));

const wrap = (ui: React.ReactElement) =>
  render(
    <ChakraProvider>
      <AuthProvider>{ui}</AuthProvider>
    </ChakraProvider>,
  );

describe("LoginPage", () => {
  it("renders email and password fields", () => {
    wrap(<LoginPage />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log in/i })).toBeInTheDocument();
  });

  it("shows link to signup", () => {
    wrap(<LoginPage />);
    expect(screen.getByText(/don't have an account/i)).toBeInTheDocument();
  });
});
