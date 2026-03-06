import { render, screen } from "@testing-library/react";
import { beforeEach, vi, type Mock } from "vitest";

import Dashboard from "./pages/Dashboard";
import { API, formatApiError } from "./api";

vi.mock("./api", () => {
  return {
    API: {
      auth: { check: vi.fn() },
      finances: { getSummary: vi.fn() },
    },
    formatApiError: vi.fn(() => "mapped-error"),
  };
});

function mockedApi() {
  return API as unknown as {
    auth: { check: Mock };
    finances: { getSummary: Mock };
  };
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows finance metrics when summary request succeeds", async () => {
    mockedApi().finances.getSummary.mockResolvedValue({
      year: 2026,
      month: 3,
      income: 2000,
      expense: 180,
      net: 1820,
      expense_by_category: { groceries: 180 },
      budgets: [
        {
          category: "groceries",
          spent: 180,
          limit: 300,
          remaining: 120,
          percentage_used: 60,
          status: "ok",
        },
      ],
    });

    render(<Dashboard />);

    expect(await screen.findByText("Depenses du mois")).toBeInTheDocument();
    expect(screen.getAllByText("180.00 EUR").length).toBeGreaterThan(0);
    expect(screen.getByText("2000.00 EUR")).toBeInTheDocument();
  });

  it("shows detailed API error when summary request fails", async () => {
    mockedApi().finances.getSummary.mockRejectedValue(new Error("backend 401"));
    (formatApiError as Mock).mockReturnValue("401 Invalid API key");

    render(<Dashboard />);

    expect(await screen.findByText("Erreur de connexion")).toBeInTheDocument();
    expect(screen.getByText("401 Invalid API key")).toBeInTheDocument();
  });
});
