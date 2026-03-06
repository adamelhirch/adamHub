import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, vi, type Mock } from "vitest";

import App from "./App";
import { API } from "./api";

vi.mock("./api", () => {
  return {
    API: {
      auth: { check: vi.fn().mockResolvedValue({ ok: true }) },
      finances: {
        getSummary: vi.fn().mockResolvedValue({
          year: 2026,
          month: 3,
          income: 1200,
          expense: 200,
          net: 1000,
          expense_by_category: {},
          budgets: [],
        }),
      },
      pantry: {
        getOverview: vi.fn().mockResolvedValue({
          total_items: 2,
          low_stock_items: 1,
          expiring_within_7_days: 0,
        }),
        listItems: vi.fn().mockResolvedValue([]),
      },
      groceries: {
        listItems: vi.fn().mockResolvedValue([]),
      },
      calendar: {
        sync: vi.fn().mockResolvedValue({ synced: 0 }),
        agenda: vi.fn().mockResolvedValue([]),
        listItems: vi.fn().mockResolvedValue([]),
      },
      mealPlans: {
        list: vi.fn().mockResolvedValue([]),
        confirmCooked: vi.fn().mockResolvedValue({}),
        unconfirmCooked: vi.fn().mockResolvedValue({}),
      },
    },
    formatApiError: vi.fn(() => "mapped-error"),
  };
});

function mockedApi() {
  return API as unknown as {
    finances: { getSummary: Mock };
    pantry: { getOverview: Mock };
    groceries: { listItems: Mock };
    calendar: { agenda: Mock };
  };
}

describe("App navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/");
  });

  it("renders sidebar routes and navigates between pages", async () => {
    render(<App />);

    expect(await screen.findByText("Bonjour Adam.")).toBeInTheDocument();
    expect(mockedApi().finances.getSummary).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("link", { name: "Finances" }));
    expect(await screen.findByRole("heading", { name: "Finances" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Pantry & Courses" }));
    expect(await screen.findByRole("heading", { name: "Pantry & Courses" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Calendrier" }));
    expect(await screen.findByRole("heading", { name: "Calendrier" })).toBeInTheDocument();
  });
});
