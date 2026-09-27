import { request } from "./api";

export type SupermarketStore = "leclerc" | "auchan" | "carrefour" | "intermarche";

export type PickupType = "quai" | "spot" | "tape" | "pieton";

export type OptimizationStrategy = "mdd" | "budget" | "bio";

export interface SupermarketStoreLocation {
  store: SupermarketStore;
  external_store_id: string;
  name: string;
  address: string;
  zipcode: string;
  city: string;
  pickup_type: PickupType;
  distance_km?: number | null;
  channel?: string | null;
}

export interface UserStorePreference {
  store: SupermarketStore;
  external_store_id: string;
  store_label: string;
  location_label?: string | null;
  pickup_type: PickupType;
  optimization_strategy: OptimizationStrategy;
  channel?: string | null;
  updated_at: string;
}

export interface UserStorePreferenceUpdate {
  external_store_id: string;
  store_label: string;
  location_label?: string | null;
  pickup_type: PickupType;
  optimization_strategy?: OptimizationStrategy;
  channel?: string | null;
  raw_context?: Record<string, unknown>;
}

export interface SubstituteProposalRead {
  id: number;
  alternative_cache_id: number;
  alternative_name: string;
  alternative_brand?: string | null;
  alternative_unit_price_cents: number;
  price_difference_cents: number;
  reason: string;
  status: "pending" | "accepted" | "rejected";
}

export interface MatchedCartItemRead {
  id: number;
  grocery_item_id?: number | null;
  cache_id?: number | null;
  external_id?: string | null;
  name: string;
  brand?: string | null;
  packaging?: string | null;
  image_url?: string | null;
  product_url?: string | null;
  quantity: number;
  unit_price_cents: number;
  total_price_cents: number;
  match_type: "exact_history" | "mdd" | "budget" | "bio" | "substitute" | "manual";
  status: "staged" | "to_modify" | "removed" | "synced";
  custom_note?: string | null;
  substitute_proposal?: SubstituteProposalRead | null;
}

export interface GroceryToCartJobRead {
  id: number;
  store: SupermarketStore;
  external_store_id: string;
  status: "draft" | "reviewing" | "syncing" | "synced" | "completed" | "failed";
  optimization_strategy: OptimizationStrategy;
  items_count: number;
  matched_count: number;
  substitutes_count: number;
  unmatched_count: number;
  estimated_total_cents: number;
  error_message?: string | null;
  synced_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
  items: MatchedCartItemRead[];
}

export interface CreateCartJobPayload {
  store: SupermarketStore;
  external_store_id?: string;
  optimization_strategy?: OptimizationStrategy;
  item_ids?: number[];
}

export interface CartAdjustment {
  matched_item_id: number;
  action: "accept_substitute" | "modify_with_note" | "remove";
  substitute_id?: number;
  custom_note?: string;
}

export interface RefineJobPayload {
  adjustments: CartAdjustment[];
}

export interface SyncJobResponse {
  id: number;
  status: string;
  synced_at: string;
  remote_cart_ref?: string | null;
  items_synced_count: number;
  message: string;
}

export interface ConfirmPickupResponse {
  id: number;
  status: string;
  completed_at: string;
  restocked_items_count: number;
  message: string;
}

// ── API Methods ──────────────────────────────────────────────────────────────

export function searchSupermarketStores(params: {
  store?: SupermarketStore;
  zipcode?: string;
  city?: string;
  latitude?: number;
  longitude?: number;
}): Promise<SupermarketStoreLocation[]> {
  const query = new URLSearchParams();
  if (params.store) query.append("store", params.store);
  if (params.zipcode) query.append("zipcode", params.zipcode);
  if (params.city) query.append("city", params.city);
  if (params.latitude !== undefined) query.append("latitude", params.latitude.toString());
  if (params.longitude !== undefined) query.append("longitude", params.longitude.toString());
  return request<SupermarketStoreLocation[]>(`/supermarket/stores/search?${query.toString()}`);
}

export function getUserStorePreferences(): Promise<UserStorePreference[]> {
  return request<UserStorePreference[]>("/supermarket/stores/preferences");
}

export function setUserStorePreference(
  store: SupermarketStore,
  payload: UserStorePreferenceUpdate,
): Promise<UserStorePreference> {
  return request<UserStorePreference>(`/supermarket/stores/preferences/${store}`, {
    method: "PUT",
    body: payload,
  });
}

export function createCartJob(payload: CreateCartJobPayload): Promise<GroceryToCartJobRead> {
  return request<GroceryToCartJobRead>("/supermarket/cart/jobs", {
    method: "POST",
    body: payload,
  });
}

export function getCartJob(id: number): Promise<GroceryToCartJobRead> {
  return request<GroceryToCartJobRead>(`/supermarket/cart/jobs/${id}`);
}

export function getActiveCartJob(): Promise<GroceryToCartJobRead | null> {
  return request<GroceryToCartJobRead | null>("/supermarket/cart/jobs/active");
}

export function refineCartJob(id: number, payload: RefineJobPayload): Promise<GroceryToCartJobRead> {
  return request<GroceryToCartJobRead>(`/supermarket/cart/jobs/${id}/refine`, {
    method: "POST",
    body: payload,
  });
}

export function syncCartJob(id: number): Promise<SyncJobResponse> {
  return request<SyncJobResponse>(`/supermarket/cart/jobs/${id}/sync`, {
    method: "POST",
  });
}

export interface UpdateMatchedItemPayload {
  status?: "staged" | "to_modify" | "removed" | "synced";
  custom_note?: string | null;
  quantity?: number;
}

export function updateCartJobItem(
  jobId: number,
  itemId: number,
  payload: UpdateMatchedItemPayload,
): Promise<MatchedCartItemRead> {
  return request<MatchedCartItemRead>(`/supermarket/cart/jobs/${jobId}/items/${itemId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function confirmPickup(id: number): Promise<ConfirmPickupResponse> {
  return request<ConfirmPickupResponse>(`/supermarket/cart/jobs/${id}/confirm-pickup`, {
    method: "POST",
  });
}

export function deleteCartJob(id: number): Promise<void> {
  return request<void>(`/supermarket/cart/jobs/${id}`, {
    method: "DELETE",
  });
}

// ── Supermarket Connections (Web In-App Login & Sync) ────────────────────────

export interface SupermarketConnectionRead {
  id: number;
  store: SupermarketStore;
  label: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
  cookies_count: number;
}

export interface SupermarketConnectionImportPayload {
  store: SupermarketStore;
  label: string;
  cookies: { name: string; value: string; domain?: string; path?: string }[];
  credentials?: { username: string; password: string };
  activate?: boolean;
  connection_id?: number;
  customer_uuid?: string;
}

export function listSupermarketConnections(store?: SupermarketStore): Promise<SupermarketConnectionRead[]> {
  const qs = store ? `?store=${store}` : "";
  return request<SupermarketConnectionRead[]>(`/supermarket/connections${qs}`);
}

export function importSupermarketConnection(
  payload: SupermarketConnectionImportPayload,
): Promise<SupermarketConnectionRead> {
  return request<SupermarketConnectionRead>("/supermarket/connections/import", {
    method: "POST",
    body: payload,
  });
}

export function activateSupermarketConnection(
  connectionId: number,
): Promise<SupermarketConnectionRead> {
  return request<SupermarketConnectionRead>(`/supermarket/connections/${connectionId}/activate`, {
    method: "PUT",
  });
}

export function deleteSupermarketConnection(
  connectionId: number,
): Promise<SupermarketConnectionRead> {
  return request<SupermarketConnectionRead>(`/supermarket/connections/${connectionId}`, {
    method: "DELETE",
  });
}

