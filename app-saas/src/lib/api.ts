import { getStoredToken, setStoredToken } from "@/lib/token-storage";

export const API_URL = (
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

interface ErrorPayload {
  detail?: string | { msg: string }[];
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const token = await getStoredToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  const data = (await response.json().catch(() => null)) as ErrorPayload | null;

  if (!response.ok) {
    const detail = data?.detail;
    let message = `Erreur ${response.status}`;
    if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail) && detail.length > 0) {
      message = detail.map((d) => d.msg).join(", ");
    }
    throw new ApiError(response.status, message);
  }

  return data as T;
}

async function authenticate(
  path: "/auth/login" | "/auth/register",
  payload: { email: string; password: string } | { email: string; password: string; display_name: string },
): Promise<AuthResponse> {
  const response = await request<AuthResponse>(path, {
    method: "POST",
    body: payload,
  });
  await setStoredToken(response.token);
  return response;
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return authenticate("/auth/login", { email, password });
}

export function register(
  email: string,
  password: string,
  displayName: string,
): Promise<AuthResponse> {
  return authenticate("/auth/register", {
    email,
    password,
    display_name: displayName,
  });
}

export function logout(): Promise<void> {
  return setStoredToken(null);
}
