"use client";

import { authApi, User } from "./api";

export function setToken(token: string) {
  localStorage.setItem("access_token", token);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function clearToken() {
  localStorage.removeItem("access_token");
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const res = await authApi.me();
    return res.data;
  } catch {
    return null;
  }
}

export function logout() {
  clearToken();
  window.location.href = "/login";
}
