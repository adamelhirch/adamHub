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

export type SupermarketStoreKey = 'intermarche' | 'carrefour' | 'leclerc' | 'auchan';

export const STORE_LABELS: Record<SupermarketStoreKey, string> = {
  intermarche: 'Intermarché',
  carrefour: 'Carrefour',
  leclerc: 'Leclerc',
  auchan: 'Auchan',
};

export interface SupermarketStoreCapabilities {
  supports_sort: boolean;
  supports_promotions: boolean;
  requires_store_selection: boolean;
  requires_login: boolean;
}

// Mirrors the connection matrix served by GET /supermarket/stores (source of
// truth: app/services/store_catalog.py STORE_REGISTRY).
export const STORE_CAPABILITIES: Record<SupermarketStoreKey, SupermarketStoreCapabilities> = {
  intermarche: { supports_sort: true, supports_promotions: true, requires_store_selection: true, requires_login: false },
  carrefour:   { supports_sort: true, supports_promotions: true, requires_store_selection: true, requires_login: false },
  leclerc:     { supports_sort: true, supports_promotions: false, requires_store_selection: true, requires_login: false },
  auchan:      { supports_sort: true, supports_promotions: false, requires_store_selection: true, requires_login: false },
};

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
  searchSupermarket: (store: SupermarketStoreKey, query: string, options?: { forceRefresh?: boolean; promotionsOnly?: boolean }) => Promise<void>;
  searchIntermarche: (query: string, forceRefresh?: boolean, promotionsOnly?: boolean) => Promise<void>;
  getCachedProducts: (query?: string, store?: SupermarketStoreKey) => Promise<void>;
  hasCachedProducts: (query: string, store?: SupermarketStoreKey) => Promise<boolean>;
  clearSearchResults: () => void;
  fetchPantryMapping: (itemId: number) => Promise<SupermarketMapping | null>;
  savePantryMapping: (itemId: number, product: SupermarketProduct) => Promise<SupermarketMapping>;
  deleteMapping: (mappingId: number) => Promise<void>;

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
    const { forceRefresh = false, promotionsOnly = false } = options;
    set({ searchLoading: true, searchError: null, searchResults: [] });
    try {
      const limit = 30;
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
}));
