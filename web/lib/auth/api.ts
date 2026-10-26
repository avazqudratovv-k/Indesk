import { apiClient } from "@/lib/api/client";
import type { User } from "@/lib/types";

// Auth endpoints never trigger a refresh on 401: a wrong password is an answer, not an expired session.
const noRefresh = { refreshOn401: false } as const;

export function signup(input: { email: string; password: string; displayName: string }): Promise<User> {
  return apiClient().request<User>("/api/auth/signup", {
    ...noRefresh,
    method: "POST",
    json: { email: input.email, password: input.password, display_name: input.displayName },
  });
}

export function login(input: { email: string; password: string }): Promise<User> {
  return apiClient().request<User>("/api/auth/login", { ...noRefresh, method: "POST", json: input });
}

export function logout(): Promise<undefined> {
  return apiClient().request("/api/auth/logout", { ...noRefresh, method: "POST" });
}

export function fetchMe(): Promise<User> {
  return apiClient().request<User>("/api/me");
}
