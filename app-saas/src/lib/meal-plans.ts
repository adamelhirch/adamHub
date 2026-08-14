import { request } from "@/lib/api";
import type { MealPlanRead } from "@/lib/api";

export type { MealPlanRead };

export interface MealIngredientConsumptionRead {
  name: string;
  unit: string;
  required_quantity: number;
  consumed_quantity: number;
  missing_quantity: number;
}

export interface MealPlanConfirmResult {
  meal_plan_id: number;
  already_confirmed: boolean;
  confirmed_at: string;
  note: string | null;
  pantry_consumption: MealIngredientConsumptionRead[];
}

export interface MealIngredientRestoreRead {
  name: string;
  unit: string;
  restored_quantity: number;
  pantry_item_id: number;
}

export interface MealPlanUnconfirmResult {
  meal_plan_id: number;
  already_unconfirmed: boolean;
  previously_confirmed_at: string | null;
  note: string | null;
  pantry_restore: MealIngredientRestoreRead[];
}

export function confirmMealPlanCooked(
  id: number,
  note?: string,
): Promise<MealPlanConfirmResult> {
  return request<MealPlanConfirmResult>(`/meal-plans/${id}/confirm-cooked`, {
    method: "POST",
    body: note !== undefined ? { note } : undefined,
  });
}

export function unconfirmMealPlanCooked(id: number): Promise<MealPlanUnconfirmResult> {
  return request<MealPlanUnconfirmResult>(`/meal-plans/${id}/unconfirm-cooked`, {
    method: "POST",
  });
}
