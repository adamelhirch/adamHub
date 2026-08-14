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

export function listRecipes(): Promise<RecipeRead[]> {
  return request<RecipeRead[]>("/recipes");
}

export function getRecipe(id: number): Promise<RecipeRead> {
  return request<RecipeRead>(`/recipes/${id}`);
}

export function deleteRecipe(id: number): Promise<DeleteRecipeResult> {
  return request<DeleteRecipeResult>(`/recipes/${id}`, { method: "DELETE" });
}
