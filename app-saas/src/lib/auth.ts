import { request, type AuthUser } from "@/lib/api";

export function me(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}
