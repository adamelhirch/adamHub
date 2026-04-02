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
    store_label?: string;
    external_id?: string;
    packaging?: string;
    price_text?: string;
    product_url?: string;
    priority?: number;
    note?: string;
  }) => Promise<void>;
  updateItem: (id: number, data: Partial<Pick<GroceryItem, 'name' | 'quantity' | 'unit' | 'category' | 'image_url' | 'store_label' | 'external_id' | 'packaging' | 'price_text' | 'product_url' | 'priority' | 'note' | 'checked'>>) => Promise<void>;
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
  updatePantryItem: (id: number, data: Partial<Pick<PantryItem, 'name' | 'quantity' | 'min_quantity' | 'expires_at' | 'location' | 'note' | 'unit' | 'category' | 'image_url' | 'store_label' | 'external_id' | 'packaging' | 'price_text' | 'product_url'>>) => Promise<void>;
  deletePantryItem: (id: number) => Promise<void>;
  consumePantryItem: (id: number, amount: number) => Promise<void>;

  // Supermarket search
  searchResults: SupermarketProduct[];
  searchLoading: boolean;
  searchError: string | null;
  pantryMappings: Record<number, SupermarketMapping | null>;

  searchIntermarche: (query: string, forceRefresh?: boolean, promotionsOnly?: boolean) => Promise<void>;
  getCachedProducts: (query?: string) => Promise<void>;
  hasCachedProducts: (query: string) => Promise<boolean>;
  clearSearchResults: () => void;
  fetchPantryMapping: (itemId: number) => Promise<SupermarketMapping | null>;
  savePantryMapping: (itemId: number, product: SupermarketProduct) => Promise<SupermarketMapping>;
  deleteMapping: (mappingId: number) => Promise<void>;
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

  searchIntermarche: async (query: string, forceRefresh = false, promotionsOnly = false) => {
    set({ searchLoading: true, searchError: null, searchResults: [] });
    try {
      if (!forceRefresh && !promotionsOnly) {
        const cached = await api.get('/supermarket/search', {
          params: {
            store: 'intermarche',
            query,
            limit: 30,
          },
        });
        if (Array.isArray(cached.data) && cached.data.length >= 30 && hasResolvedCategories(cached.data)) {
          set({ searchResults: cached.data });
          return;
        }
      }

      const res = await api.post(
        '/supermarket/search',
        {
          store: 'intermarche',
          queries: [query],
          max_results: 30,
          promotions_only: promotionsOnly,
        },
        {
          timeout: 120_000,
        }
      );
      set({ searchResults: res.data });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erreur lors de la recherche';
      set({ searchError: msg });
    } finally {
      set({ searchLoading: false });
    }
  },

  getCachedProducts: async (query) => {
    set({ searchLoading: true, searchError: null });
    try {
      const res = await api.get('/supermarket/search', {
        params: {
          store: 'intermarche',
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

  hasCachedProducts: async (query) => {
    if (!query.trim()) {
      return false;
    }
    const res = await api.get('/supermarket/search', {
      params: {
        store: 'intermarche',
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
    const res = await api.put(`/supermarket/mappings/pantry-items/${itemId}`, {
      cache_id: product.cache_id,
      store: product.store,
      external_id: product.external_id,
      store_label: product.store === 'intermarche' ? 'Intermarché' : product.store,
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
}));
