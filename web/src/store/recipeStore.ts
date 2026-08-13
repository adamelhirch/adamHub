import { create } from 'zustand';
import api from '../lib/api';

export type RecipeIngredient = {
  id: number;
  recipe_id: number;
  name: string;
  quantity: number;
  unit: string;
  note: string | null;
  store: string | null;
  store_label: string | null;
  external_id: string | null;
  category: string | null;
  packaging: string | null;
  price_text: string | null;
  product_url: string | null;
  image_url: string | null;
};

export type Recipe = {
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
  ingredients: RecipeIngredient[];
  created_at: string;
  updated_at: string;
};

export type MissingIngredient = {
  name: string;
  needed_quantity: number;
  available_quantity: number;
  missing_quantity: number;
  unit: string;
};

export type MealPlan = {
  id: number;
  planned_at: string;
  planned_for: string | null;
  slot: 'breakfast' | 'lunch' | 'dinner' | null;
  recipe_id: number;
  recipe_name: string;
  servings_override: number | null;
  note: string | null;
  auto_add_missing_ingredients: boolean;
  synced_grocery_at: string | null;
  cooked: boolean;
  cooked_at: string | null;
  cooked_note: string | null;
  missing_ingredients: MissingIngredient[];
  created_at: string;
  updated_at: string;
};

export type RecipeIngredientInput = {
  name: string;
  quantity: number;
  unit: string;
  note: string | null;
  store: string | null;
  store_label: string | null;
  external_id: string | null;
  category: string | null;
  packaging: string | null;
  price_text: string | null;
  product_url: string | null;
  image_url: string | null;
};

export type RecipeInput = {
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
  ingredients: RecipeIngredientInput[];
};

export type MealPlanInput = {
  recipe_id: number;
  planned_at: string;
  servings_override: number | null;
  note: string | null;
  auto_add_missing_ingredients: boolean;
};

export type ConfirmCookedResult = {
  recipe_name: string;
  missing_ingredients: Array<{ name: string; missing_quantity: number }>;
  pantry_consumption: Array<{ name: string; consumed_quantity: number }>;
};

interface RecipeStore {
  recipes: Recipe[];
  mealPlans: MealPlan[];
  recipesLoading: boolean;
  mealPlansLoading: boolean;
  error: string | null;

  fetchRecipes: () => Promise<void>;
  createRecipe: (data: RecipeInput) => Promise<void>;
  updateRecipe: (id: number, data: Partial<RecipeInput>) => Promise<void>;
  deleteRecipe: (id: number) => Promise<void>;
  confirmRecipeCooked: (id: number) => Promise<ConfirmCookedResult>;

  fetchMealPlans: (limit?: number) => Promise<void>;
  createMealPlan: (data: MealPlanInput) => Promise<void>;
  updateMealPlan: (id: number, data: Partial<MealPlanInput>) => Promise<void>;
  deleteMealPlan: (id: number) => Promise<void>;
  syncMealPlanGroceries: (id: number) => Promise<{ created_grocery_items: number }>;
  confirmMealPlanCooked: (id: number) => Promise<{ pantry_consumption: Array<{ consumed_quantity: number }> }>;
  unconfirmMealPlanCooked: (id: number) => Promise<{ pantry_restore: Array<{ restored_quantity: number }> }>;
}

export const useRecipeStore = create<RecipeStore>((set, get) => ({
  recipes: [],
  mealPlans: [],
  recipesLoading: false,
  mealPlansLoading: false,
  error: null,

  fetchRecipes: async () => {
    set({ recipesLoading: true, error: null });
    try {
      const response = await api.get('/recipes');
      set({ recipes: response.data, recipesLoading: false });
    } catch (error: any) {
      set({ error: error.message ?? 'Failed to fetch recipes', recipesLoading: false });
      console.error('Failed to fetch recipes', error);
      throw error;
    }
  },

  createRecipe: async (data) => {
    try {
      await api.post('/recipes', data);
      await get().fetchRecipes();
    } catch (error) {
      console.error('Failed to create recipe', error);
      throw error;
    }
  },

  updateRecipe: async (id, data) => {
    try {
      await api.patch(`/recipes/${id}`, data);
      await get().fetchRecipes();
    } catch (error) {
      console.error('Failed to update recipe', error);
      throw error;
    }
  },

  deleteRecipe: async (id) => {
    try {
      await api.delete(`/recipes/${id}`);
      await get().fetchRecipes();
    } catch (error) {
      console.error('Failed to delete recipe', error);
      throw error;
    }
  },

  confirmRecipeCooked: async (id) => {
    try {
      const response = await api.post(`/recipes/${id}/confirm-cooked`, {});
      return response.data;
    } catch (error) {
      console.error('Failed to confirm recipe cooked', error);
      throw error;
    }
  },

  fetchMealPlans: async (limit = 100) => {
    set({ mealPlansLoading: true, error: null });
    try {
      const response = await api.get('/meal-plans', { params: { limit } });
      set({ mealPlans: response.data, mealPlansLoading: false });
    } catch (error: any) {
      set({ error: error.message ?? 'Failed to fetch meal plans', mealPlansLoading: false });
      console.error('Failed to fetch meal plans', error);
      throw error;
    }
  },

  createMealPlan: async (data) => {
    try {
      await api.post('/meal-plans', data);
      await Promise.all([get().fetchMealPlans(), get().fetchRecipes()]);
    } catch (error) {
      console.error('Failed to create meal plan', error);
      throw error;
    }
  },

  updateMealPlan: async (id, data) => {
    try {
      await api.patch(`/meal-plans/${id}`, data);
      await Promise.all([get().fetchMealPlans(), get().fetchRecipes()]);
    } catch (error) {
      console.error('Failed to update meal plan', error);
      throw error;
    }
  },

  deleteMealPlan: async (id) => {
    try {
      await api.delete(`/meal-plans/${id}`);
      await get().fetchMealPlans();
    } catch (error) {
      console.error('Failed to delete meal plan', error);
      throw error;
    }
  },

  syncMealPlanGroceries: async (id) => {
    try {
      const response = await api.post(`/meal-plans/${id}/sync-groceries`);
      await get().fetchMealPlans();
      return response.data;
    } catch (error) {
      console.error('Failed to sync meal plan groceries', error);
      throw error;
    }
  },

  confirmMealPlanCooked: async (id) => {
    try {
      const response = await api.post(`/meal-plans/${id}/confirm-cooked`, {});
      await get().fetchMealPlans();
      return response.data;
    } catch (error) {
      console.error('Failed to confirm meal plan cooked', error);
      throw error;
    }
  },

  unconfirmMealPlanCooked: async (id) => {
    try {
      const response = await api.post(`/meal-plans/${id}/unconfirm-cooked`);
      await get().fetchMealPlans();
      return response.data;
    } catch (error) {
      console.error('Failed to unconfirm meal plan cooked', error);
      throw error;
    }
  },
}));
