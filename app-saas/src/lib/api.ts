import { getStoredToken, setStoredToken } from "@/lib/token-storage";
import type { RecipeRead } from "./recipes";

export const API_URL = (
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  data?: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
}

export interface ApiKeyRead {
  api_key: string | null;
  created_at: string | null;
}

export function getApiKey(): Promise<ApiKeyRead> {
  return request<ApiKeyRead>("/auth/api-key");
}

export function generateApiKey(): Promise<ApiKeyRead> {
  return request<ApiKeyRead>("/auth/api-key", { method: "POST" });
}

export function revokeApiKey(): Promise<void> {
  return request<void>("/auth/api-key", { method: "DELETE" });
}

export interface NtfyTopicRead {
  ntfy_topic: string | null;
}

export function getNtfyTopic(): Promise<NtfyTopicRead> {
  return request<NtfyTopicRead>("/auth/notifications");
}

export function setNtfyTopic(ntfy_topic: string | null): Promise<NtfyTopicRead> {
  return request<NtfyTopicRead>("/auth/notifications", {
    method: "PUT",
    body: { ntfy_topic },
  });
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

interface ErrorPayload {
  detail?: string | { msg: string }[];
}

export async function request<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const token = await getStoredToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  const data = (await response.json().catch(() => null)) as ErrorPayload | null;

  if (!response.ok) {
    const detail = data?.detail;
    let message = `Erreur ${response.status}`;
    if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail) && detail.length > 0) {
      message = detail.map((d) => d.msg).join(", ");
    }
    throw new ApiError(response.status, message, data);
  }

  return data as T;
}

async function authenticate(
  path: "/auth/login" | "/auth/register",
  payload: { email: string; password: string } | { email: string; password: string; display_name: string },
): Promise<AuthResponse> {
  const response = await request<AuthResponse>(path, {
    method: "POST",
    body: payload,
  });
  await setStoredToken(response.token);
  return response;
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return authenticate("/auth/login", { email, password });
}

export function register(
  email: string,
  password: string,
  displayName: string,
): Promise<AuthResponse> {
  return authenticate("/auth/register", {
    email,
    password,
    display_name: displayName,
  });
}

export function logout(): Promise<void> {
  return setStoredToken(null);
}

export interface MealPlanRead {
  id: number;
  planned_at: string;
  planned_for: string | null;
  slot: "breakfast" | "lunch" | "dinner" | null;
  recipe_id: number;
  recipe_name: string;
  servings_override: number | null;
  note: string | null;
  cooked: boolean;
  synced_grocery_at: string | null;
  created_at: string;
  updated_at: string;
}

export function listMealPlans(params: { date_from?: string; date_to?: string } = {}): Promise<MealPlanRead[]> {
  const query = new URLSearchParams();
  if (params.date_from) query.set("date_from", params.date_from);
  if (params.date_to) query.set("date_to", params.date_to);
  const qs = query.toString();
  return request<MealPlanRead[]>(`/meal-plans${qs ? `?${qs}` : ""}`);
}

export interface MealPlanSyncGroceriesResult {
  meal_plan_id: number;
  created_grocery_items: number;
  missing_ingredients: unknown[];
}

export function syncMealPlanGroceries(id: number): Promise<MealPlanSyncGroceriesResult> {
  return request<MealPlanSyncGroceriesResult>(`/meal-plans/${id}/sync-groceries`, { method: "POST" });
}

export interface GroceryItemRead {
  id: number;
  name: string;
  quantity: number;
  unit: string;
  category: string | null;
  checked: boolean;
  in_cart?: boolean;
  priority: number;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export function listGroceryItems(): Promise<GroceryItemRead[]> {
  return request<GroceryItemRead[]>("/groceries");
}

export interface GroceryItemUpdatePayload {
  name?: string;
  quantity?: number;
  unit?: string;
  checked?: boolean;
  category?: string | null;
  note?: string | null;
}

export function updateGroceryItem(
  id: number,
  payload: GroceryItemUpdatePayload,
): Promise<GroceryItemRead> {
  return request<GroceryItemRead>(`/groceries/${id}`, { method: "PATCH", body: payload });
}

export interface PantryItemRead {
  id: number;
  name: string;
  quantity: number;
  unit: string;
  category: string | null;
  min_quantity: number;
  expires_at: string | null;
  location: string | null;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export function listPantryItems(): Promise<PantryItemRead[]> {
  return request<PantryItemRead[]>("/pantry/items");
}

export {
  type RecipeIngredientRead,
  type RecipeRead,
  type RecipeCookResult,
  type RecipeUncookResult,
  type RecipeAddToGroceriesRequest,
  type RecipeAddToGroceriesResult,
  type CalendarConflictDetail,
  type AlternativeSlot,
  type MealPlanConflictResponse,
  listRecipes,
  getRecipe,
  deleteRecipe,
  updateRecipe,
  confirmRecipeCooked,
  unconfirmRecipeCooked,
  addRecipeToGroceries,
  scheduleMealPlan,
} from "./recipes";

export interface RecipeIngredientInput {
  name: string;
  quantity: number;
  unit: string;
}

export interface RecipeCreateInput {
  name: string;
  instructions: string;
  servings: number;
  prep_minutes?: number;
  cook_minutes?: number;
  ingredients: RecipeIngredientInput[];
}

export function createRecipe(payload: RecipeCreateInput): Promise<RecipeRead> {
  return request<RecipeRead>("/recipes", { method: "POST", body: payload });
}

export interface MealPlanCreateInput {
  recipe_id: number;
  planned_for: string;
  slot: "breakfast" | "lunch" | "dinner";
}

export function createMealPlan(payload: MealPlanCreateInput): Promise<MealPlanRead> {
  return request<MealPlanRead>("/meal-plans", { method: "POST", body: payload });
}

// ---------------------------------------------------------------------------
// Tasks API
// ---------------------------------------------------------------------------

export type TaskStatus = "todo" | "in_progress" | "done" | "cancelled";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export interface TaskRead {
  id: number;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  due_at: string | null;
  estimated_minutes: number | null;
  created_at: string;
  updated_at: string;
}

export function listTasks(params: { only_open?: boolean; status?: TaskStatus; limit?: number } = {}): Promise<TaskRead[]> {
  const query = new URLSearchParams();
  if (params.only_open !== undefined) query.set("only_open", String(params.only_open));
  if (params.status) query.set("status", params.status);
  if (params.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return request<TaskRead[]>(`/tasks${qs ? `?${qs}` : ""}`);
}

export function createTask(payload: {
  title: string;
  description?: string;
  priority?: TaskPriority;
  due_at?: string;
}): Promise<TaskRead> {
  return request<TaskRead>("/tasks", { method: "POST", body: payload });
}

export function updateTask(
  id: number,
  payload: { status?: TaskStatus; title?: string; priority?: TaskPriority; description?: string },
): Promise<TaskRead> {
  return request<TaskRead>(`/tasks/${id}`, { method: "PATCH", body: payload });
}

export function completeTask(id: number): Promise<TaskRead> {
  return request<TaskRead>(`/tasks/${id}/complete`, { method: "POST" });
}

export function deleteTask(id: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/tasks/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Calendar API
// ---------------------------------------------------------------------------

export interface CalendarItemRead {
  id: number;
  title: string;
  description: string | null;
  start_at: string;
  end_at: string;
  all_day: boolean;
  category: string;
  source: string;
  completed: boolean;
  notification_enabled: boolean;
}

export function listCalendarAgenda(day?: string, includeCompleted = true): Promise<CalendarItemRead[]> {
  const query = new URLSearchParams();
  if (day) query.set("day", day);
  query.set("include_completed", String(includeCompleted));
  const qs = query.toString();
  return request<CalendarItemRead[]>(`/calendar/agenda${qs ? `?${qs}` : ""}`);
}

export function listCalendarItems(params: { from_at?: string; to_at?: string; limit?: number } = {}): Promise<CalendarItemRead[]> {
  const query = new URLSearchParams();
  if (params.from_at) query.set("from_at", params.from_at);
  if (params.to_at) query.set("to_at", params.to_at);
  if (params.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return request<CalendarItemRead[]>(`/calendar/items${qs ? `?${qs}` : ""}`);
}

// ---------------------------------------------------------------------------
// Fitness API
// ---------------------------------------------------------------------------

export interface FitnessSessionExercise {
  name: string;
  sets?: number;
  reps?: number;
  weight_kg?: number;
  duration_seconds?: number;
}

export interface FitnessSessionRead {
  id: number;
  title: string;
  session_type: string;
  planned_at: string;
  started_at: string | null;
  ended_at: string | null;
  duration_minutes: number;
  status: "planned" | "in_progress" | "completed" | "skipped";
  notes: string | null;
  exercises: FitnessSessionExercise[];
}

export interface FitnessOverviewStats {
  planned_sessions: number;
  upcoming_sessions: number;
  completed_sessions_30d: number;
  completion_rate_30d: number;
  avg_duration_minutes: number | null;
  latest_body_weight_kg: number | null;
}

export interface FitnessOverviewRead {
  stats: FitnessOverviewStats;
  upcoming_sessions: FitnessSessionRead[];
  recent_sessions: FitnessSessionRead[];
}

export function getFitnessOverview(): Promise<FitnessOverviewRead> {
  return request<FitnessOverviewRead>("/fitness");
}

export function listFitnessSessions(limit = 50): Promise<FitnessSessionRead[]> {
  return request<FitnessSessionRead[]>(`/fitness/sessions?limit=${limit}`);
}

export function createFitnessSession(payload: {
  title: string;
  planned_at: string;
  duration_minutes?: number;
  session_type?: string;
  notes?: string;
}): Promise<FitnessSessionRead> {
  return request<FitnessSessionRead>("/fitness/sessions", { method: "POST", body: payload });
}

// ---------------------------------------------------------------------------
// Finances & Subscriptions API
// ---------------------------------------------------------------------------

export interface FinanceTransactionRead {
  id: number;
  amount: number;
  label: string;
  category: string;
  kind: "expense" | "income";
  occurred_at: string;
  notes: string | null;
}

export interface FinanceMonthSummary {
  year: number;
  month: number;
  income: number;
  expense: number;
  net: number;
  expense_by_category: Record<string, number>;
}

export function getFinanceSummary(year: number, month: number): Promise<FinanceMonthSummary> {
  return request<FinanceMonthSummary>(`/finances/summary?year=${year}&month=${month}`);
}

export function listFinanceTransactions(limit = 50): Promise<FinanceTransactionRead[]> {
  return request<FinanceTransactionRead[]>(`/finances/transactions?limit=${limit}`);
}

export interface SubscriptionRead {
  id: number;
  name: string;
  amount: number;
  frequency: "monthly" | "yearly" | "weekly";
  category: string;
  next_due_date: string;
  active: boolean;
}

export function listSubscriptions(): Promise<SubscriptionRead[]> {
  return request<SubscriptionRead[]>("/subscriptions");
}

