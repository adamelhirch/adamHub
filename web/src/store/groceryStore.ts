import { create } from 'zustand';
import api from '../lib/api';

// ─── Fix float as number ──────────────────────────────────────────────────────
type float = number;

// ─── Types ────────────────────────────────────────────────────────────────────

export interface GroceryItem {
  id: number;
  name: string;
  quantity: float;
  unit: string;
  category: string | null;
  image_url: string | null;
  store_label: string | null;
  external_id: string | null;
  packaging: string | null;
  price_text: string | null;
  product_url: string | null;
  checked: boolean;
  priority: number;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface PantryItem {
  id: number;
  name: string;
  quantity: float;
  unit: string;
  category: string | null;
  image_url: string | null;
  store_label: string | null;
  external_id: string | null;
  packaging: string | null;
  price_text: string | null;
  product_url: string | null;
  min_quantity: float;
  expires_at: string | null;
  location: string | null;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface PantryOverview {
  total_items: number;
  low_stock_items: number;
  expiring_within_7_days: number;
}

export type SupermarketStoreKey = 'intermarche' | 'ubereats' | 'carrefour';

export type UbereatsSortKey = 'recommended' | 'price_asc' | 'price_desc';

export const STORE_LABELS: Record<SupermarketStoreKey, string> = {
  intermarche: 'Intermarché',
  ubereats: 'Uber Eats',
  carrefour: 'Carrefour',
};

export interface UbereatsLocation {
  label: string | null;
  title: string | null;
  formatted_address: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface UbereatsStoreOption {
  uuid: string;
  name: string;
  subtitle: string | null;
  address: string | null;
  rating: number | null;
  image_url: string | null;
}

export interface UbereatsStoreSelection {
  external_store_id: string;
  store_label: string;
  location_label: string | null;
  updated_at: string;
}

export interface UbereatsGeocodeResult {
  title: string;
  subtitle: string | null;
  formatted_address: string;
  latitude: number;
  longitude: number;
  reference: string | null;
  reference_type: string;
}

export interface UbereatsSavedAddress {
  id: number;
  label: string;
  formatted_address: string;
  subtitle: string | null;
  latitude: number;
  longitude: number;
  reference: string | null;
  reference_type: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UbereatsCartItem {
  item_uuid: string;
  cart_item_uuid: string;
  title: string;
  quantity: number;
  price_cents: number | null;
  image_url: string | null;
}

export interface UbereatsCartDetails {
  draft_order_uuid: string | null;
  cart_uuid: string | null;
  store_uuid: string | null;
  items: UbereatsCartItem[];
}

export interface UbereatsCartSummaryEntry {
  draft_order_uuid: string | null;
  title: string | null;
  subtotal_text: string | null;
  item_count: number | null;
  store_image_urls: string[];
  details: UbereatsCartDetails | null;
}

export interface UbereatsCartSummary {
  carts: UbereatsCartSummaryEntry[];
  focused: UbereatsCartDetails | null;
}

export interface UbereatsPastOrder {
  uuid: string;
  store_title: string | null;
  store_image_url: string | null;
  completed_at: string | null;
  is_completed: boolean;
  is_cancelled: boolean;
  num_items: number;
  total_quantity: number;
  total_text: string | null;
}

export interface UbereatsImportedItem {
  name: string;
  quantity: number;
  external_id: string | null;
  price_text: string | null;
  created: boolean;
}

export interface UbereatsImportResult {
  order_uuid: string;
  store_label: string | null;
  items_imported: number;
  items_updated: number;
  items: UbereatsImportedItem[];
}

export interface SupermarketConnection {
  id: number;
  store: SupermarketStoreKey;
  label: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
  cookies_count: number;
}

export interface SupermarketProduct {
  cache_id: number;
  query: string;
  brand: string | null;
  category: string | null;
  name: string;
  packaging: string | null;
  price_amount: float | null;
  price_text: string | null;
  image_url: string | null;
  store: string;
  external_id: string | null;
  product_url: string | null;
  fetched_at: string;
  expires_at: string;
}

export interface SupermarketMapping {
  id: number;
  target_type: 'recipe_ingredient' | 'pantry_item';
  target_id: number;
  store: string;
  cache_id?: number | null;
  external_id: string;
  store_label: string;
  name_snapshot: string;
  category_snapshot: string | null;
  packaging_snapshot: string | null;
  price_snapshot: string | null;
  product_url: string | null;
  image_url: string | null;
  last_verified_at: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

function hasResolvedCategories(products: SupermarketProduct[]): boolean {
  return products.some((product) => Boolean(product.category?.trim()));
}

function extractErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string };
    if (first && typeof first.msg === 'string') {
      return first.msg;
    }
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

// ─── Store Interface ──────────────────────────────────────────────────────────

interface GroceryStore {
  // Grocery list
  items: GroceryItem[];
  groceryLoading: boolean;

  fetchItems: () => Promise<void>;
  addItem: (data: {
    name: string;
    quantity?: number;
    unit?: string;
    category?: string;
    image_url?: string;
    cache_id?: number;
    store_label?: string;
    external_id?: string;
    packaging?: string;
    price_text?: string;
    product_url?: string;
    priority?: number;
    note?: string;
  }) => Promise<void>;
  updateItem: (id: number, data: Partial<Pick<GroceryItem, 'name' | 'quantity' | 'unit' | 'category' | 'image_url' | 'store_label' | 'external_id' | 'packaging' | 'price_text' | 'product_url' | 'priority' | 'note' | 'checked'>> & { cache_id?: number }) => Promise<void>;
  toggleCheck: (id: number, checked: boolean) => Promise<void>;
  deleteItem: (id: number) => Promise<void>;
  clearChecked: () => Promise<void>;

  // Pantry
  pantryItems: PantryItem[];
  pantryOverview: PantryOverview | null;
  pantryLoading: boolean;

  fetchPantry: () => Promise<void>;
  fetchPantryOverview: () => Promise<void>;
  addPantryItem: (data: {
    name: string;
    quantity?: number;
    unit?: string;
    category?: string;
    image_url?: string;
    cache_id?: number;
    store_label?: string;
    external_id?: string;
    packaging?: string;
    price_text?: string;
    product_url?: string;
    min_quantity?: number;
    expires_at?: string;
    location?: string;
    note?: string;
  }) => Promise<PantryItem>;
  updatePantryItem: (id: number, data: Partial<Pick<PantryItem, 'name' | 'quantity' | 'min_quantity' | 'expires_at' | 'location' | 'note' | 'unit' | 'category' | 'image_url' | 'store_label' | 'external_id' | 'packaging' | 'price_text' | 'product_url'>> & { cache_id?: number }) => Promise<void>;
  deletePantryItem: (id: number) => Promise<void>;
  consumePantryItem: (id: number, amount: number) => Promise<void>;

  // Supermarket search
  searchResults: SupermarketProduct[];
  searchLoading: boolean;
  searchError: string | null;
  pantryMappings: Record<number, SupermarketMapping | null>;
  selectedStore: SupermarketStoreKey;

  setSelectedStore: (store: SupermarketStoreKey) => void;
  searchSupermarket: (store: SupermarketStoreKey, query: string, options?: { forceRefresh?: boolean; promotionsOnly?: boolean; sortBy?: UbereatsSortKey }) => Promise<void>;
  searchIntermarche: (query: string, forceRefresh?: boolean, promotionsOnly?: boolean) => Promise<void>;
  getCachedProducts: (query?: string, store?: SupermarketStoreKey) => Promise<void>;
  hasCachedProducts: (query: string, store?: SupermarketStoreKey) => Promise<boolean>;
  clearSearchResults: () => void;
  fetchPantryMapping: (itemId: number) => Promise<SupermarketMapping | null>;
  savePantryMapping: (itemId: number, product: SupermarketProduct) => Promise<SupermarketMapping>;
  deleteMapping: (mappingId: number) => Promise<void>;

  // Uber Eats setup
  ubereatsLocation: UbereatsLocation | null;
  ubereatsSelectedStore: UbereatsStoreSelection | null;
  ubereatsStores: UbereatsStoreOption[];
  ubereatsStoresLoading: boolean;
  ubereatsError: string | null;

  fetchUbereatsLocation: () => Promise<void>;
  updateUbereatsLocation: (payload: {
    title: string;
    subtitle?: string;
    formatted_address?: string;
    latitude: number;
    longitude: number;
    reference?: string;
    reference_type?: string;
  }) => Promise<void>;
  fetchUbereatsStores: (limit?: number) => Promise<void>;
  fetchSelectedUbereatsStore: () => Promise<void>;
  selectUbereatsStore: (option: UbereatsStoreOption) => Promise<void>;

  // Saved addresses + geocoding
  ubereatsAddresses: UbereatsSavedAddress[];
  ubereatsGeocodeResults: UbereatsGeocodeResult[];
  ubereatsGeocodeLoading: boolean;

  fetchUbereatsAddresses: () => Promise<void>;
  geocodeUbereatsAddress: (query: string) => Promise<void>;
  clearUbereatsGeocodeResults: () => void;
  saveUbereatsAddress: (
    payload: {
      label: string;
      formatted_address: string;
      subtitle?: string;
      latitude: number;
      longitude: number;
      reference?: string;
      reference_type?: string;
      activate?: boolean;
    },
  ) => Promise<UbereatsSavedAddress>;
  activateUbereatsAddress: (addressId: number) => Promise<void>;
  deleteUbereatsAddress: (addressId: number) => Promise<void>;

  // Cart automation
  ubereatsCart: UbereatsCartSummary | null;
  ubereatsCartAdding: Record<number, boolean>;
  ubereatsCartError: string | null;

  fetchUbereatsCart: (options?: { includeDetails?: boolean }) => Promise<void>;
  addToUbereatsCart: (cacheId: number, quantity?: number) => Promise<void>;

  // Past orders & import
  ubereatsPastOrders: UbereatsPastOrder[];
  ubereatsPastOrdersLoading: boolean;
  ubereatsImportLoading: boolean;
  ubereatsLastImport: UbereatsImportResult | null;
  ubereatsImportError: string | null;

  fetchUbereatsPastOrders: (limit?: number) => Promise<void>;
  importUbereatsOrderToPantry: (trackingUrlOrUuid: string) => Promise<UbereatsImportResult>;
  clearUbereatsImportFeedback: () => void;

  // Cookie connections (per-store, multi-account)
  connections: SupermarketConnection[];
  connectionsLoading: boolean;
  fetchConnections: () => Promise<void>;
  activateConnection: (connectionId: number) => Promise<void>;
  deleteConnection: (connectionId: number) => Promise<void>;
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useGroceryStore = create<GroceryStore>((set, get) => ({
  // ── Grocery ──────────────────────────────────────────────────────────────────
  items: [],
  groceryLoading: false,

  fetchItems: async () => {
    set({ groceryLoading: true });
    try {
      const res = await api.get('/groceries');
      set({ items: res.data });
    } finally {
      set({ groceryLoading: false });
    }
  },

  addItem: async (data) => {
    const res = await api.post('/groceries', data);
    set((s) => ({ items: [res.data, ...s.items] }));
  },

  updateItem: async (id, data) => {
    const res = await api.patch(`/groceries/${id}`, data);
    set((s) => ({ items: s.items.map((item) => (item.id === id ? res.data : item)) }));
  },

  toggleCheck: async (id, checked) => {
    // Optimistic update
    set((s) => ({ items: s.items.map((i) => (i.id === id ? { ...i, checked } : i)) }));
    try {
      const res = await api.patch(`/groceries/${id}`, { checked });
      set((s) => ({ items: s.items.map((i) => (i.id === id ? res.data : i)) }));
      if (checked) {
        await Promise.all([get().fetchPantry(), get().fetchPantryOverview()]);
      }
    } catch {
      // Revert on error
      set((s) => ({ items: s.items.map((i) => (i.id === id ? { ...i, checked: !checked } : i)) }));
    }
  },

  deleteItem: async (id) => {
    await api.delete(`/groceries/${id}`);
    set((s) => ({ items: s.items.filter((i) => i.id !== id) }));
  },

  clearChecked: async () => {
    const checked = get().items.filter((i) => i.checked);
    await Promise.all(checked.map((i) => api.delete(`/groceries/${i.id}`)));
    set((s) => ({ items: s.items.filter((i) => !i.checked) }));
  },

  // ── Pantry ───────────────────────────────────────────────────────────────────
  pantryItems: [],
  pantryOverview: null,
  pantryLoading: false,

  fetchPantry: async () => {
    set({ pantryLoading: true });
    try {
      const res = await api.get('/pantry/items');
      set({ pantryItems: res.data });
    } finally {
      set({ pantryLoading: false });
    }
  },

  fetchPantryOverview: async () => {
    const res = await api.get('/pantry/overview');
    set({ pantryOverview: res.data });
  },

  addPantryItem: async (data) => {
    const res = await api.post('/pantry/items', data);
    set((s) => ({ pantryItems: [res.data, ...s.pantryItems] }));
    return res.data;
  },

  updatePantryItem: async (id, data) => {
    const res = await api.patch(`/pantry/items/${id}`, data);
    set((s) => ({ pantryItems: s.pantryItems.map((p) => (p.id === id ? res.data : p)) }));
  },

  deletePantryItem: async (id) => {
    await api.delete(`/pantry/items/${id}`);
    set((s) => ({ pantryItems: s.pantryItems.filter((p) => p.id !== id) }));
  },

  consumePantryItem: async (id, amount) => {
    const res = await api.post(`/pantry/items/${id}/consume`, { amount });
    set((s) => ({ pantryItems: s.pantryItems.map((p) => (p.id === id ? res.data : p)) }));
  },

  // ── Supermarket search ────────────────────────────────────────────────────────
  searchResults: [],
  searchLoading: false,
  searchError: null,
  pantryMappings: {},
  selectedStore: 'intermarche',

  setSelectedStore: (store) => {
    set({ selectedStore: store, searchResults: [], searchError: null });
  },

  searchSupermarket: async (store, query, options = {}) => {
    const { forceRefresh = false, promotionsOnly = false, sortBy } = options;
    set({ searchLoading: true, searchError: null, searchResults: [] });
    try {
      const limit = store === 'ubereats' ? 100 : 30;
      const supportsCacheReuse = store === 'intermarche';
      if (supportsCacheReuse && !forceRefresh && !promotionsOnly) {
        const cached = await api.get('/supermarket/search', {
          params: { store, query, limit },
        });
        if (Array.isArray(cached.data) && cached.data.length >= limit && hasResolvedCategories(cached.data)) {
          set({ searchResults: cached.data });
          return;
        }
      }

      const body: Record<string, unknown> = {
        store,
        queries: [query],
        max_results: limit,
      };
      if (store === 'intermarche') {
        body.promotions_only = promotionsOnly;
      }
      if (store === 'ubereats' && sortBy && sortBy !== 'recommended') {
        body.sort_by = sortBy;
      }

      const res = await api.post('/supermarket/search', body, { timeout: 120_000 });
      set({ searchResults: res.data });
    } catch (e: unknown) {
      set({ searchError: extractErrorMessage(e, 'Erreur lors de la recherche') });
    } finally {
      set({ searchLoading: false });
    }
  },

  searchIntermarche: async (query, forceRefresh = false, promotionsOnly = false) => {
    await get().searchSupermarket('intermarche', query, { forceRefresh, promotionsOnly });
  },

  getCachedProducts: async (query, store) => {
    set({ searchLoading: true, searchError: null });
    try {
      const res = await api.get('/supermarket/search', {
        params: {
          store: store || get().selectedStore,
          query: query || undefined,
        },
      });
      set({ searchResults: Array.isArray(res.data) ? res.data : [] });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erreur';
      set({ searchError: msg });
    } finally {
      set({ searchLoading: false });
    }
  },

  hasCachedProducts: async (query, store) => {
    if (!query.trim()) {
      return false;
    }
    const res = await api.get('/supermarket/search', {
      params: {
        store: store || get().selectedStore,
        query,
        limit: 1,
      },
    });
    return Array.isArray(res.data) && res.data.length > 0;
  },

  clearSearchResults: () => set({ searchResults: [], searchError: null }),

  fetchPantryMapping: async (itemId) => {
    const res = await api.get(`/supermarket/mappings/pantry-items/${itemId}`);
    set((s) => ({
      pantryMappings: {
        ...s.pantryMappings,
        [itemId]: res.data,
      },
    }));
    return res.data;
  },

  savePantryMapping: async (itemId, product) => {
    const storeKey = product.store as SupermarketStoreKey;
    const storeLabel = STORE_LABELS[storeKey] ?? product.store;
    const res = await api.put(`/supermarket/mappings/pantry-items/${itemId}`, {
      cache_id: product.cache_id,
      store: product.store,
      external_id: product.external_id,
      store_label: storeLabel,
      name_snapshot: product.name,
      category_snapshot: product.category,
      packaging_snapshot: product.packaging,
      price_snapshot: product.price_text,
      product_url: product.product_url,
      image_url: product.image_url,
    });
    set((s) => ({
      pantryMappings: {
        ...s.pantryMappings,
        [itemId]: res.data,
      },
    }));
    return res.data;
  },

  deleteMapping: async (mappingId) => {
    const res = await api.delete(`/supermarket/mappings/${mappingId}`);
    const deleted = res.data as SupermarketMapping;
    if (deleted.target_type === 'pantry_item') {
      set((s) => ({
        pantryMappings: {
          ...s.pantryMappings,
          [deleted.target_id]: null,
        },
      }));
    }
  },

  // ── Uber Eats setup ────────────────────────────────────────────────────────
  ubereatsLocation: null,
  ubereatsSelectedStore: null,
  ubereatsStores: [],
  ubereatsStoresLoading: false,
  ubereatsError: null,

  fetchUbereatsLocation: async () => {
    try {
      const res = await api.get('/supermarket/ubereats/location');
      set({ ubereatsLocation: res.data });
    } catch (e: unknown) {
      set({ ubereatsError: extractErrorMessage(e, 'Erreur localisation') });
    }
  },

  updateUbereatsLocation: async (payload) => {
    try {
      const res = await api.put('/supermarket/ubereats/location', payload);
      set({ ubereatsLocation: res.data, ubereatsError: null });
    } catch (e: unknown) {
      const msg = extractErrorMessage(e, 'Erreur mise à jour adresse');
      set({ ubereatsError: msg });
      throw new Error(msg);
    }
  },

  fetchUbereatsStores: async (limit = 25) => {
    set({ ubereatsStoresLoading: true, ubereatsError: null });
    try {
      const res = await api.get('/supermarket/ubereats/stores', { params: { limit }, timeout: 60_000 });
      set({ ubereatsStores: res.data });
    } catch (e: unknown) {
      set({ ubereatsError: extractErrorMessage(e, 'Erreur listing magasins'), ubereatsStores: [] });
    } finally {
      set({ ubereatsStoresLoading: false });
    }
  },

  fetchSelectedUbereatsStore: async () => {
    try {
      const res = await api.get('/supermarket/ubereats/selected-store');
      set({ ubereatsSelectedStore: res.data });
    } catch {
      set({ ubereatsSelectedStore: null });
    }
  },

  selectUbereatsStore: async (option) => {
    const res = await api.put('/supermarket/ubereats/selected-store', {
      external_store_id: option.uuid,
      store_label: option.name,
      location_label: option.address,
    });
    set({ ubereatsSelectedStore: res.data, ubereatsError: null });
  },

  // ── Saved addresses + geocoding ────────────────────────────────────────────
  ubereatsAddresses: [],
  ubereatsGeocodeResults: [],
  ubereatsGeocodeLoading: false,

  fetchUbereatsAddresses: async () => {
    try {
      const res = await api.get('/supermarket/ubereats/addresses');
      set({ ubereatsAddresses: Array.isArray(res.data) ? res.data : [] });
    } catch (e: unknown) {
      set({ ubereatsError: extractErrorMessage(e, 'Erreur adresses') });
    }
  },

  geocodeUbereatsAddress: async (query) => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      set({ ubereatsGeocodeResults: [], ubereatsGeocodeLoading: false });
      return;
    }
    set({ ubereatsGeocodeLoading: true });
    try {
      const res = await api.get('/supermarket/ubereats/geocode', { params: { q: trimmed, limit: 6 } });
      set({ ubereatsGeocodeResults: Array.isArray(res.data) ? res.data : [] });
    } catch (e: unknown) {
      set({ ubereatsError: extractErrorMessage(e, 'Erreur géocodage'), ubereatsGeocodeResults: [] });
    } finally {
      set({ ubereatsGeocodeLoading: false });
    }
  },

  clearUbereatsGeocodeResults: () => set({ ubereatsGeocodeResults: [] }),

  saveUbereatsAddress: async (payload) => {
    const res = await api.post('/supermarket/ubereats/addresses', payload);
    const created = res.data as UbereatsSavedAddress;
    await get().fetchUbereatsAddresses();
    if (created.is_active) {
      await get().fetchUbereatsLocation();
    }
    return created;
  },

  activateUbereatsAddress: async (addressId) => {
    await api.put(`/supermarket/ubereats/addresses/${addressId}/activate`);
    await get().fetchUbereatsAddresses();
    await get().fetchUbereatsLocation();
  },

  deleteUbereatsAddress: async (addressId) => {
    await api.delete(`/supermarket/ubereats/addresses/${addressId}`);
    await get().fetchUbereatsAddresses();
  },

  // ── Cart automation ────────────────────────────────────────────────────────
  ubereatsCart: null,
  ubereatsCartAdding: {},
  ubereatsCartError: null,

  fetchUbereatsCart: async (options) => {
    const includeDetails = options?.includeDetails ?? false;
    try {
      const res = await api.get('/supermarket/ubereats/cart', {
        params: { include_details: includeDetails },
        timeout: 30_000,
      });
      set({ ubereatsCart: res.data, ubereatsCartError: null });
    } catch (e: unknown) {
      set({ ubereatsCartError: extractErrorMessage(e, 'Erreur lecture panier UE') });
    }
  },

  ubereatsPastOrders: [],
  ubereatsPastOrdersLoading: false,
  ubereatsImportLoading: false,
  ubereatsLastImport: null,
  ubereatsImportError: null,

  fetchUbereatsPastOrders: async (limit = 10) => {
    set({ ubereatsPastOrdersLoading: true });
    try {
      const res = await api.get('/supermarket/ubereats/orders', { params: { limit }, timeout: 30_000 });
      set({ ubereatsPastOrders: Array.isArray(res.data) ? res.data : [] });
    } catch (e: unknown) {
      set({ ubereatsImportError: extractErrorMessage(e, 'Erreur lecture commandes UE') });
    } finally {
      set({ ubereatsPastOrdersLoading: false });
    }
  },

  importUbereatsOrderToPantry: async (trackingUrlOrUuid) => {
    set({ ubereatsImportLoading: true, ubereatsImportError: null, ubereatsLastImport: null });
    try {
      const res = await api.post(
        '/supermarket/ubereats/orders/import-to-pantry',
        { tracking_url_or_uuid: trackingUrlOrUuid },
        { timeout: 60_000 },
      );
      const result = res.data as UbereatsImportResult;
      set({ ubereatsLastImport: result });
      await get().fetchPantry();
      await get().fetchPantryOverview();
      return result;
    } catch (e: unknown) {
      const msg = extractErrorMessage(e, 'Erreur import commande UE');
      set({ ubereatsImportError: msg });
      throw new Error(msg);
    } finally {
      set({ ubereatsImportLoading: false });
    }
  },

  clearUbereatsImportFeedback: () => set({ ubereatsLastImport: null, ubereatsImportError: null }),

  // ── Connections (per-store cookie sets) ─────────────────────────────────
  connections: [],
  connectionsLoading: false,

  fetchConnections: async () => {
    set({ connectionsLoading: true });
    try {
      const res = await api.get('/supermarket/connections');
      set({ connections: Array.isArray(res.data) ? res.data : [] });
    } catch {
      set({ connections: [] });
    } finally {
      set({ connectionsLoading: false });
    }
  },

  activateConnection: async (connectionId) => {
    await api.put(`/supermarket/connections/${connectionId}/activate`);
    await get().fetchConnections();
  },

  deleteConnection: async (connectionId) => {
    await api.delete(`/supermarket/connections/${connectionId}`);
    await get().fetchConnections();
  },

  addToUbereatsCart: async (cacheId, quantity = 1) => {
    set((s) => ({ ubereatsCartAdding: { ...s.ubereatsCartAdding, [cacheId]: true }, ubereatsCartError: null }));
    try {
      await api.post('/supermarket/ubereats/cart/items', { cache_id: cacheId, quantity }, { timeout: 30_000 });
      // Refresh both the live UE cart and the local grocery list (mirrored by backend).
      await Promise.all([get().fetchUbereatsCart(), get().fetchItems()]);
    } catch (e: unknown) {
      set({ ubereatsCartError: extractErrorMessage(e, 'Erreur ajout au panier UE') });
      throw e;
    } finally {
      set((s) => {
        const next = { ...s.ubereatsCartAdding };
        delete next[cacheId];
        return { ubereatsCartAdding: next };
      });
    }
  },
}));
