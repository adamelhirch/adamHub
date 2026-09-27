import { request } from "@/lib/api";

export interface RecipeIngredientRead {
  id: number;
  recipe_id: number;
  name: string;
  quantity: number;
  unit: string;
  note: string | null;
  cache_id: number | null;
  store: string | null;
  store_label: string | null;
  external_id: string | null;
  category: string | null;
  packaging: string | null;
  price_text: string | null;
  product_url: string | null;
  image_url: string | null;
}

export interface RecipeRead {
  id: number;
  name: string;
  description: string | null;
  instructions: string;
  steps: string[];
  utensils: string[];
  prep_minutes: number;
  cook_minutes: number;
  servings: number;
  tags: string[];
  source_url: string | null;
  source_platform: string | null;
  source_title: string | null;
  source_description: string | null;
  source_transcript: string | null;
  ingredients: RecipeIngredientRead[];
  created_at: string;
  updated_at: string;
}

export interface DeleteRecipeResult {
  ok: boolean;
  deleted_id: number;
}

export interface MissingIngredientRead {
  name: string;
  needed_quantity: number;
  available_quantity: number;
  missing_quantity: number;
  unit: string;
  store: string | null;
  store_label: string | null;
  external_id: string | null;
  category: string | null;
  packaging: string | null;
  price_text: string | null;
  product_url: string | null;
  image_url: string | null;
}

export interface MealIngredientConsumptionRead {
  name: string;
  unit: string;
  required_quantity: number;
  consumed_quantity: number;
  missing_quantity: number;
}

export interface RecipeCookResult {
  recipe_id: number;
  recipe_name: string;
  cooked_at: string;
  note: string | null;
  missing_ingredients: MissingIngredientRead[];
  pantry_consumption: MealIngredientConsumptionRead[];
  meal_plan_id: number | null;
  already_confirmed: boolean;
}

export interface MealIngredientRestoreRead {
  name: string;
  unit: string;
  restored_quantity: number;
  pantry_item_id: number;
}

export interface RecipeUncookResult {
  recipe_id: number;
  recipe_name: string;
  already_unconfirmed: boolean;
  previously_confirmed_at: string | null;
  note: string | null;
  pantry_restore: MealIngredientRestoreRead[];
}

export interface RecipeAddToGroceriesRequest {
  ingredient_ids?: number[];
  servings_override?: number;
  missing_only?: boolean;
}

export interface RecipeAddToGroceriesResult {
  recipe_id: number;
  added_count: number;
  items: {
    id: number;
    name: string;
    quantity: number;
    unit: string;
    category: string | null;
    checked: boolean;
    recipe_id?: number;
  }[];
}

export interface CalendarConflictDetail {
  title: string;
  start_at: string;
  end_at: string;
  category: string;
}

export interface AlternativeSlot {
  start_at: string;
  end_at: string;
  label: string;
}

export interface MealPlanConflictResponse {
  detail: string;
  conflict: boolean;
  colliding_items: CalendarConflictDetail[];
  suggested_slots: AlternativeSlot[];
}

export function listRecipes(): Promise<RecipeRead[]> {
  return request<RecipeRead[]>("/recipes");
}

export function getRecipe(id: number): Promise<RecipeRead> {
  return request<RecipeRead>(`/recipes/${id}`);
}

export function updateRecipe(id: number, payload: Partial<RecipeRead>): Promise<RecipeRead> {
  return request<RecipeRead>(`/recipes/${id}`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteRecipe(id: number): Promise<DeleteRecipeResult> {
  return request<DeleteRecipeResult>(`/recipes/${id}`, { method: "DELETE" });
}

export function confirmRecipeCooked(
  recipeId: number,
  options?: { servings_override?: number; note?: string }
): Promise<RecipeCookResult> {
  return request<RecipeCookResult>(`/recipes/${recipeId}/confirm-cooked`, {
    method: "POST",
    body: options ?? {},
  });
}

export function unconfirmRecipeCooked(recipeId: number): Promise<RecipeUncookResult> {
  return request<RecipeUncookResult>(`/recipes/${recipeId}/unconfirm-cooked`, {
    method: "POST",
  });
}

export function addRecipeToGroceries(
  recipeId: number,
  payload: RecipeAddToGroceriesRequest = {}
): Promise<RecipeAddToGroceriesResult> {
  return request<RecipeAddToGroceriesResult>(`/recipes/${recipeId}/add-to-groceries`, {
    method: "POST",
    body: payload,
  });
}

export function scheduleMealPlan(payload: {
  recipe_id: number;
  planned_at: string;
  servings_override?: number;
  note?: string;
  auto_add_missing_ingredients?: boolean;
}): Promise<any> {
  return request<any>("/meal-plans", {
    method: "POST",
    body: payload,
  });
}
