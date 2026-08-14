import { request } from "@/lib/api";

export interface SupermarketSearchResult {
  cache_id: number;
  store: string;
  query: string;
  external_id: string | null;
  name: string;
  brand: string | null;
  category: string | null;
  packaging: string | null;
  price_amount: number | null;
  price_text: string | null;
  image_url: string | null;
  product_url: string | null;
  fetched_at: string;
  expires_at: string;
}

export interface SupermarketSearchPayload {
  store: string;
  queries: string[];
  max_results?: number;
}

export function searchSupermarket(
  payload: SupermarketSearchPayload,
): Promise<SupermarketSearchResult[]> {
  return request<SupermarketSearchResult[]>("/supermarket/search", {
    method: "POST",
    body: payload,
  });
}
