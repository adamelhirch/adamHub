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
