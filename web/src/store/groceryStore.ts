import { create } from 'zustand';
import api, { cartApi } from '../lib/api';
import type {
  CartStatus,
  SupermarketCart,
  SupermarketCartItemAddPayload,
} from '../lib/api';

export type { CartStatus, SupermarketCart, SupermarketCartItem } from '../lib/api';

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

// Stores whose search requires a branché account connection (cookies). Auchan
// is excluded: it works without login via the filesystem cookie fallback.
export const ACCOUNT_REQUIRED_STORES: SupermarketStoreKey[] = ['intermarche', 'carrefour', 'leclerc'];

// One selectable Auchan store, as served by GET /supermarket/auchan/offering-contexts.
export interface AuchanOfferingContext {
  pos_id: string | null;
  pos_type: string | null;
  seller_id: string;
  store_reference: string | null;
  channel: string | null;
  name: string | null;
  address: string | null;
  distance: string | null;
}

// Persisted Auchan store selection (GET/POST /supermarket/auchan/selected-store).
export interface AuchanSelectedStore {
  external_store_id: string;
  store_label: string;
  location_label: string | null;
  updated_at: string;
}

// Payload for POST /supermarket/auchan/selected-store.
export interface AuchanStoreSelectionPayload {
  seller_id: string;
  store_reference: string;
  channel?: string;
  store_label: string;
  location_label?: string | null;
  zipcode?: string | null;
  city?: string | null;
  country?: string | null;
  latitude?: number | null;
  longitude?: number | null;
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

function isNotFoundError(error: unknown): boolean {
  return (error as { response?: { status?: number } })?.response?.status === 404;
}

// ─── Intermarché mirror cart errors ───────────────────────────────────────────
//
// The Intermarché cart endpoints are a mirror of the store's real site cart
// (b2). When the mirror fails the local cart can no longer reflect the site, so
// instead of surfacing the raw adapter error we explain the cause and invite
// the user to resync the cookies in the extension. The three other stores keep
// the plain local error messages (Run 1 behavior).

const INTERMARCHE_SESSION_EXPIRED_MESSAGE =
  "La session Intermarché a expiré : le panier ne peut plus être synchronisé avec le site. " +
  'Resynchronise les cookies dans l\'extension AdamHUB Connect (déconnexion puis reconnexion du compte Intermarché) puis réessaie.';

const INTERMARCHE_UNAVAILABLE_MESSAGE =
  "Le site Intermarché n'a pas répondu (session expirée ou protection anti-bot). " +
  "Resynchronise les cookies dans l'extension AdamHUB Connect puis réessaie.";

const INTERMARCHE_NOT_FOUND_MESSAGE =
  "Le panier Intermarché est introuvable sur le site (compte ou magasin incorrect). " +
  "Vérifie et resynchronise la connexion dans l'extension AdamHUB Connect.";

const INTERMARCHE_CONFLICT_MESSAGE =
  'Le panier Intermarché est désynchronisé du site. ' +
  'Clique sur « Resynchroniser » pour recharger le panier réel puis réessaie.';

export function extractCartErrorMessage(
  store: SupermarketStoreKey,
  error: unknown,
  fallback: string,
): string {
  if (store !== 'intermarche') {
    return extractErrorMessage(error, fallback);
  }
  const status = (error as { response?: { status?: number } })?.response?.status;
  if (status === 401 || status === 403) {
    return INTERMARCHE_SESSION_EXPIRED_MESSAGE;
  }
  if (status === 503) {
    return INTERMARCHE_UNAVAILABLE_MESSAGE;
  }
  if (status === 404) {
    return INTERMARCHE_NOT_FOUND_MESSAGE;
  }
  if (status === 409) {
    return INTERMARCHE_CONFLICT_MESSAGE;
  }
  return extractErrorMessage(error, fallback);
}

// Replace (or append) a cart in a list by identity (id) or, for a freshly
// upserted cart that is not yet in the list, by store.
function upsertCartIn(carts: SupermarketCart[], cart: SupermarketCart): SupermarketCart[] {
  const index = carts.findIndex((c) => c.id === cart.id || c.store === cart.store);
  if (index === -1) {
    return [...carts, cart];
  }
  const next = [...carts];
  next[index] = cart;
  return next;
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

  // Auchan store selection (no login required)
  auchanContexts: AuchanOfferingContext[];
  auchanSelectedStore: AuchanSelectedStore | null;
  auchanLoading: boolean;
  auchanError: string | null;
  fetchAuchanOfferingContexts: (zipcode: string, city: string, lat: number, lng: number) => Promise<void>;
  selectAuchanStore: (payload: AuchanStoreSelectionPayload) => Promise<void>;
  fetchSelectedAuchanStore: () => Promise<void>;
  clearAuchanStore: () => void;

  // Cart (panier) — one draft/validated cart per store
  carts: SupermarketCart[];
  cartsByStore: Record<SupermarketStoreKey, SupermarketCart | null>;
  cartLoading: boolean;
  cartError: string | null;

  fetchCarts: () => Promise<void>;
  fetchCart: (store: SupermarketStoreKey) => Promise<SupermarketCart | null>;
  addCartItem: (store: SupermarketStoreKey, data: SupermarketCartItemAddPayload) => Promise<void>;
  updateCartItemQuantity: (store: SupermarketStoreKey, itemId: number, quantity: number) => Promise<void>;
  removeCartItem: (store: SupermarketStoreKey, itemId: number) => Promise<void>;
  clearCart: (store: SupermarketStoreKey) => Promise<void>;
  setCartStatus: (store: SupermarketStoreKey, status: CartStatus) => Promise<void>;
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
      // Explicit pre-checks: never let an account-less store or an Auchan
      // search without a selected store fail silently on the POST /search.
      const hasConnection = get().connections.some((c) => c.store === store);
      if (store !== 'auchan' && !hasConnection) {
        set({
          searchLoading: false,
          searchError: `Compte requis : branche une connexion ${STORE_LABELS[store]} via l'extension AdamHUB Connect pour rechercher les prix.`,
          searchResults: [],
        });
        return;
      }
      if (store === 'auchan' && !get().auchanSelectedStore) {
        set({
          searchLoading: false,
          searchError: 'Sélectionne un magasin Auchan avant de lancer une recherche.',
          searchResults: [],
        });
        return;
      }

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

  // ── Auchan store selection (works without login) ─────────────────────
  auchanContexts: [],
  auchanSelectedStore: null,
  auchanLoading: false,
  auchanError: null,

  fetchAuchanOfferingContexts: async (zipcode, city, lat, lng) => {
    set({ auchanLoading: true, auchanError: null, auchanContexts: [] });
    try {
      const res = await api.get('/supermarket/auchan/offering-contexts', {
        params: { zipcode, city, latitude: lat, longitude: lng, country: 'France' },
      });
      set({ auchanContexts: Array.isArray(res.data) ? res.data : [] });
    } catch (e: unknown) {
      set({ auchanContexts: [], auchanError: extractErrorMessage(e, 'Erreur lors de la recherche des magasins Auchan') });
    } finally {
      set({ auchanLoading: false });
    }
  },

  selectAuchanStore: async (payload) => {
    set({ auchanLoading: true, auchanError: null });
    try {
      const res = await api.post('/supermarket/auchan/selected-store', payload);
      set({ auchanSelectedStore: res.data, auchanContexts: [], searchResults: [], searchError: null });
    } catch (e: unknown) {
      set({ auchanError: extractErrorMessage(e, 'Erreur lors de la sélection du magasin Auchan') });
    } finally {
      set({ auchanLoading: false });
    }
  },

  fetchSelectedAuchanStore: async () => {
    try {
      const res = await api.get('/supermarket/auchan/selected-store');
      set({ auchanSelectedStore: res.data ?? null });
    } catch {
      set({ auchanSelectedStore: null });
    }
  },

  clearAuchanStore: () => {
    set({
      auchanSelectedStore: null,
      auchanContexts: [],
      auchanError: null,
      searchResults: [],
      searchError: null,
    });
  },

  // ── Cart (panier) ─────────────────────────────────────────────────────────────
  carts: [],
  cartsByStore: { intermarche: null, carrefour: null, leclerc: null, auchan: null },
  cartLoading: false,
  cartError: null,

  fetchCarts: async () => {
    set({ cartLoading: true, cartError: null });
    try {
      const carts = await cartApi.list();
      set((s) => {
        const cartsByStore = { ...s.cartsByStore };
        for (const cart of carts) {
          cartsByStore[cart.store as SupermarketStoreKey] = cart;
        }
        return { carts, cartsByStore };
      });
    } catch (e: unknown) {
      set({ cartError: extractErrorMessage(e, 'Erreur lors du chargement des paniers') });
    } finally {
      set({ cartLoading: false });
    }
  },

  fetchCart: async (store) => {
    set({ cartLoading: true, cartError: null });
    try {
      const cart = await cartApi.get(store);
      set((s) => ({
        carts: upsertCartIn(s.carts, cart),
        cartsByStore: { ...s.cartsByStore, [store]: cart },
      }));
      return cart;
    } catch (e: unknown) {
      // A 404 means the store has no cart yet for the local-only stores:
      // represent it as `null` rather than an error so consumers render an
      // empty cart. For the Intermarché mirror a 404 is a real site-side
      // failure (customer/cart unknown) and must surface as an error.
      if (isNotFoundError(e) && store !== 'intermarche') {
        set((s) => ({ cartsByStore: { ...s.cartsByStore, [store]: null } }));
      } else {
        set({ cartError: extractCartErrorMessage(store, e, 'Erreur lors du chargement du panier') });
      }
      return null;
    } finally {
      set({ cartLoading: false });
    }
  },

  addCartItem: async (store, data) => {
    set({ cartLoading: true, cartError: null });
    try {
      const cart = await cartApi.addItem(store, data);
      set((s) => ({
        carts: upsertCartIn(s.carts, cart),
        cartsByStore: { ...s.cartsByStore, [store]: cart },
      }));
    } catch (e: unknown) {
      set({ cartError: extractCartErrorMessage(store, e, "Erreur lors de l'ajout au panier") });
    } finally {
      set({ cartLoading: false });
    }
  },

  updateCartItemQuantity: async (store, itemId, quantity) => {
    set({ cartLoading: true, cartError: null });
    try {
      const cart = await cartApi.updateItemQuantity(store, itemId, quantity);
      set((s) => ({
        carts: upsertCartIn(s.carts, cart),
        cartsByStore: { ...s.cartsByStore, [store]: cart },
      }));
    } catch (e: unknown) {
      set({ cartError: extractCartErrorMessage(store, e, 'Erreur lors de la mise à jour de la quantité') });
    } finally {
      set({ cartLoading: false });
    }
  },

  removeCartItem: async (store, itemId) => {
    set({ cartLoading: true, cartError: null });
    try {
      const cart = await cartApi.removeItem(store, itemId);
      set((s) => ({
        carts: upsertCartIn(s.carts, cart),
        cartsByStore: { ...s.cartsByStore, [store]: cart },
      }));
    } catch (e: unknown) {
      set({ cartError: extractCartErrorMessage(store, e, "Erreur lors de la suppression de l'article") });
    } finally {
      set({ cartLoading: false });
    }
  },

  clearCart: async (store) => {
    set({ cartLoading: true, cartError: null });
    try {
      const cart = await cartApi.clear(store);
      set((s) => ({
        carts: upsertCartIn(s.carts, cart),
        cartsByStore: { ...s.cartsByStore, [store]: cart },
      }));
    } catch (e: unknown) {
      set({ cartError: extractCartErrorMessage(store, e, 'Erreur lors du vidage du panier') });
    } finally {
      set({ cartLoading: false });
    }
  },

  setCartStatus: async (store, status) => {
    set({ cartLoading: true, cartError: null });
    try {
      const cart = await cartApi.setStatus(store, status);
      set((s) => ({
        carts: upsertCartIn(s.carts, cart),
        cartsByStore: { ...s.cartsByStore, [store]: cart },
      }));
    } catch (e: unknown) {
      set({ cartError: extractCartErrorMessage(store, e, 'Erreur lors de la mise à jour du statut') });
    } finally {
      set({ cartLoading: false });
    }
  },
}));
