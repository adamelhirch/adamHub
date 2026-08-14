import { request, type GroceryItemRead } from "@/lib/api";

export interface GroceryItemCreateInput {
  name: string;
  quantity?: number;
  unit?: string;
  category?: string | null;
  note?: string | null;
}

export function createGroceryItem(payload: GroceryItemCreateInput): Promise<GroceryItemRead> {
  return request<GroceryItemRead>("/groceries", { method: "POST", body: payload });
}

export function deleteGroceryItem(id: number): Promise<{ ok: boolean; deleted_id: number }> {
  return request<{ ok: boolean; deleted_id: number }>(`/groceries/${id}`, { method: "DELETE" });
}
