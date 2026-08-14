import { request, type PantryItemRead } from "@/lib/api";

export interface PantryItemCreateInput {
  name: string;
  quantity?: number;
  unit?: string;
  category?: string | null;
  min_quantity?: number;
  expires_at?: string | null;
  location?: string | null;
  note?: string | null;
  cache_id?: number;
}

export interface PantryItemUpdateInput {
  name?: string;
  quantity?: number;
  unit?: string;
  category?: string | null;
  min_quantity?: number;
  expires_at?: string | null;
  location?: string | null;
  note?: string | null;
}

export interface PantryItemDeleteResult {
  ok: boolean;
  deleted_id: number;
}

export function createPantryItem(payload: PantryItemCreateInput): Promise<PantryItemRead> {
  return request<PantryItemRead>("/pantry/items", { method: "POST", body: payload });
}

export function updatePantryItem(
  id: number,
  payload: PantryItemUpdateInput,
): Promise<PantryItemRead> {
  return request<PantryItemRead>(`/pantry/items/${id}`, { method: "PATCH", body: payload });
}

export function consumePantryItem(id: number, amount: number): Promise<PantryItemRead> {
  return request<PantryItemRead>(`/pantry/items/${id}/consume`, {
    method: "POST",
    body: { amount },
  });
}

export function deletePantryItem(id: number): Promise<PantryItemDeleteResult> {
  return request<PantryItemDeleteResult>(`/pantry/items/${id}`, { method: "DELETE" });
}
