import axios from "axios";

import { getApiConfig } from "./config";

export type FinanceMonthSummary = {
  year: number;
  month: number;
  income: number;
  expense: number;
  net: number;
  expense_by_category: Record<string, number>;
  budgets: Array<{
    category: string;
    spent: number;
    limit: number;
    remaining: number;
    percentage_used: number;
    status: "ok" | "warning" | "exceeded";
  }>;
};

export type PantryOverview = {
  total_items: number;
  low_stock_items: number;
  expiring_within_7_days: number;
};

export type PantryItem = {
  id: number;
  name: string;
  quantity: number;
  unit: string;
  category: string | null;
  min_quantity: number;
};

export type GroceryItem = {
  id: number;
  name: string;
  quantity: number;
  unit: string;
  checked: boolean;
  category: string | null;
  priority: number;
  note: string | null;
};

export type CalendarItem = {
  id: number;
  title: string;
  description: string | null;
  start_at: string;
  end_at: string;
  category: string;
  source: string;
  source_ref_id: number | null;
  completed: boolean;
  generated: boolean;
};

export type MealPlan = {
  id: number;
  planned_for: string;
  slot: "breakfast" | "lunch" | "dinner";
  recipe_id: number;
  recipe_name: string;
  cooked: boolean;
  cooked_at: string | null;
};

export function buildRuntimeRequestConfig() {
  const { apiUrl, apiKey } = getApiConfig();
  return {
    baseURL: apiUrl,
    apiKey,
  };
}

export function formatApiError(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return "Unexpected error";
  }

  if (error.response?.data) {
    const body = error.response.data as { detail?: unknown } | string;
    if (typeof body === "string") return body;
    if (typeof body.detail === "string") return body.detail;
    if (body.detail !== undefined) return JSON.stringify(body.detail);
  }

  if (error.code === "ECONNABORTED") return "Timeout contacting API";
  if (error.message.includes("Network Error")) return "Network error / CORS";
  return error.message || "API request failed";
}

export const api = axios.create({
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 10_000,
});

api.interceptors.request.use((config) => {
  const runtime = buildRuntimeRequestConfig();
  config.baseURL = runtime.baseURL;
  if (runtime.apiKey) {
    config.headers["X-API-Key"] = runtime.apiKey;
  }
  return config;
});

export const API = {
  auth: {
    check: () => api.get<{ ok: boolean }>("/api/v1/auth/check").then((res) => res.data),
  },
  finances: {
    getSummary: (year: number, month: number) =>
      api
        .get<FinanceMonthSummary>("/api/v1/finances/summary", { params: { year, month } })
        .then((res) => res.data),
  },
  pantry: {
    getOverview: (days = 7) =>
      api.get<PantryOverview>("/api/v1/pantry/overview", { params: { days } }).then((res) => res.data),
    listItems: (params?: { low_stock_only?: boolean; expiring_in_days?: number; limit?: number }) =>
      api.get<PantryItem[]>("/api/v1/pantry/items", { params }).then((res) => res.data),
  },
  groceries: {
    listItems: (params?: { checked?: boolean; limit?: number }) =>
      api.get<GroceryItem[]>("/api/v1/groceries", { params }).then((res) => res.data),
    updateItem: (itemId: number, payload: Partial<Pick<GroceryItem, "checked" | "quantity" | "unit" | "priority" | "category" | "note">>) =>
      api.patch<GroceryItem>(`/api/v1/groceries/${itemId}`, payload).then((res) => res.data),
  },
  calendar: {
    sync: () => api.post("/api/v1/calendar/sync").then((res) => res.data),
    agenda: (day?: string) => api.get<CalendarItem[]>("/api/v1/calendar/agenda", { params: { day } }).then((res) => res.data),
    listItems: (params?: { from_at?: string; to_at?: string; include_completed?: boolean; limit?: number }) =>
      api.get<CalendarItem[]>("/api/v1/calendar/items", { params }).then((res) => res.data),
  },
  mealPlans: {
    list: (params?: { date_from?: string; date_to?: string; limit?: number }) =>
      api.get<MealPlan[]>("/api/v1/meal-plans", { params }).then((res) => res.data),
    confirmCooked: (mealPlanId: number, note?: string) =>
      api.post(`/api/v1/meal-plans/${mealPlanId}/confirm-cooked`, { note }).then((res) => res.data),
    unconfirmCooked: (mealPlanId: number) =>
      api.post(`/api/v1/meal-plans/${mealPlanId}/unconfirm-cooked`).then((res) => res.data),
  },
};
