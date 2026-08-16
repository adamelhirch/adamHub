import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_URL?.trim() || "/api/v1";
const apiKey = import.meta.env.VITE_API_KEY?.trim();

const TOKEN_STORAGE_KEY = "adamhub_token";

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // ignore (safari private mode etc.)
  }
}

// Create an Axios instance with base configuration
export const api = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  },
});

// Attach the JWT to every request when present.
api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto-redirect to /login on 401 (except for the auth endpoints themselves).
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      const url: string = error?.config?.url ?? "";
      if (!url.includes("/auth/")) {
        // The /supermarket endpoints proxy third-party sessions: a 401 there
        // usually means the *supermarket* session (cookies) expired, not the
        // app token. Only treat it as an app-auth failure (and redirect to
        // /login) when the response carries one of the backend's auth errors,
        // so the cart UI can surface a cookie-resync message instead (b3
        // Intermarché mirror).
        const detail: unknown = error?.response?.data?.detail;
        const isAppAuthFailure =
          typeof detail === "string" &&
          /token expired|invalid token|missing authorization bearer|malformed token|user no longer exists|not authorized|not authenticated|could not validate credentials/i.test(detail);
        if (!url.includes("/supermarket/") || isAppAuthFailure) {
          setStoredToken(null);
          if (typeof window !== "undefined" && window.location.pathname !== "/login") {
            window.location.href = "/login";
          }
        }
      }
    }
    return Promise.reject(error);
  },
);

// ─── Supermarket cart (panier) ──────────────────────────────────────────────
//
// Wire types mirror app/schemas/supermarket.py SupermarketCartRead /
// SupermarketCartItemRead. The store field is the backend SupermarketStore enum
// ("intermarche" | "carrefour" | "leclerc" | "auchan") but is kept as a plain
// string here, matching the existing SupermarketProduct.store precedent.

export type CartStatus = 'draft' | 'validated';

export interface SupermarketCartItem {
  id: number;
  cache_id: number | null;
  external_id: string | null;
  name: string;
  brand: string | null;
  packaging: string | null;
  price_amount: number | null;
  price_text: string | null;
  image_url: string | null;
  product_url: string | null;
  quantity: number;
}

export interface SupermarketCart {
  id: number;
  store: string;
  status: CartStatus;
  validated_at: string | null;
  external_cart_ref: string | null;
  created_at: string;
  updated_at: string;
  items: SupermarketCartItem[];
}

export interface SupermarketCartItemAddPayload {
  cache_id: number;
  quantity?: number;
}

// Typed client for the /supermarket/carts endpoints. Every mutation returns the
// full, updated cart, matching the backend response_model=SupermarketCartRead.
// A 404 (unknown item / absent cart) surfaces as a rejected Axios error so the
// store layer can map it to a `null` cart rather than a generic failure.
export const cartApi = {
  list: async (): Promise<SupermarketCart[]> => {
    const res = await api.get<SupermarketCart[]>('/supermarket/carts');
    return res.data;
  },

  get: async (store: string): Promise<SupermarketCart> => {
    const res = await api.get<SupermarketCart>(`/supermarket/carts/${store}`);
    return res.data;
  },

  addItem: async (
    store: string,
    payload: SupermarketCartItemAddPayload,
  ): Promise<SupermarketCart> => {
    const res = await api.post<SupermarketCart>(`/supermarket/carts/${store}/items`, payload);
    return res.data;
  },

  updateItemQuantity: async (
    store: string,
    itemId: number,
    quantity: number,
  ): Promise<SupermarketCart> => {
    const res = await api.patch<SupermarketCart>(
      `/supermarket/carts/${store}/items/${itemId}`,
      { quantity },
    );
    return res.data;
  },

  removeItem: async (store: string, itemId: number): Promise<SupermarketCart> => {
    const res = await api.delete<SupermarketCart>(`/supermarket/carts/${store}/items/${itemId}`);
    return res.data;
  },

  clear: async (store: string): Promise<SupermarketCart> => {
    const res = await api.delete<SupermarketCart>(`/supermarket/carts/${store}`);
    return res.data;
  },

  setStatus: async (store: string, status: CartStatus): Promise<SupermarketCart> => {
    const res = await api.put<SupermarketCart>(`/supermarket/carts/${store}/status`, { status });
    return res.data;
  },
};

export default api;

