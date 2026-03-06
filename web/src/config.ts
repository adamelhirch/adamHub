const DEFAULT_API_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const DEFAULT_API_KEY = "change-me";

export const STORAGE_KEYS = {
  apiUrl: "adamhub_api_url",
  apiKey: "adamhub_api_key",
} as const;

export type ApiConfig = {
  apiUrl: string;
  apiKey: string;
};

const memoryStorage = new Map<string, string>();

function hasBrowserStorage(): boolean {
  if (typeof window === "undefined") return false;
  const storage = window.localStorage as Storage | undefined;
  return Boolean(
    storage &&
      typeof storage.getItem === "function" &&
      typeof storage.setItem === "function" &&
      typeof storage.clear === "function",
  );
}

function readStorage(key: string): string | null {
  if (hasBrowserStorage()) {
    return window.localStorage.getItem(key);
  }
  return memoryStorage.get(key) ?? null;
}

function writeStorage(key: string, value: string): void {
  if (hasBrowserStorage()) {
    window.localStorage.setItem(key, value);
    return;
  }
  memoryStorage.set(key, value);
}

export function clearApiConfigStorage(): void {
  if (hasBrowserStorage()) {
    window.localStorage.clear();
    return;
  }
  memoryStorage.clear();
}

export function normalizeApiUrl(value: string): string {
  const trimmed = String(value || "").trim().replace(/\/+$/, "");
  if (!trimmed) return DEFAULT_API_URL;
  if (trimmed.endsWith("/api/v1")) return trimmed.slice(0, -7);
  return trimmed;
}

export function normalizeApiKey(value: string): string {
  return String(value || "").trim();
}

export function getApiConfig(): ApiConfig {
  const rawUrl = readStorage(STORAGE_KEYS.apiUrl) || DEFAULT_API_URL;
  const rawKey = readStorage(STORAGE_KEYS.apiKey) || DEFAULT_API_KEY;
  return {
    apiUrl: normalizeApiUrl(rawUrl),
    apiKey: normalizeApiKey(rawKey),
  };
}

export function saveApiConfig(next: ApiConfig): ApiConfig {
  const normalized = {
    apiUrl: normalizeApiUrl(next.apiUrl),
    apiKey: normalizeApiKey(next.apiKey),
  };
  writeStorage(STORAGE_KEYS.apiUrl, normalized.apiUrl);
  writeStorage(STORAGE_KEYS.apiKey, normalized.apiKey);
  return normalized;
}
