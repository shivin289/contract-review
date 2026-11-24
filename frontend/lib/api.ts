"use client";
import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

/** Every request carries the Clerk session token; the backend verifies it. */
export function useApi() {
  const { getToken } = useAuth();

  const call = useCallback(async (path: string, init: RequestInit = {}) => {
    const token = await getToken();
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${token}`);
    return fetch(`${API_URL}${path}`, { ...init, headers });
  }, [getToken]);

  const json = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const res = await call(path, init);
    if (!res.ok) {
      let msg = res.statusText;
      try { const d = (await res.json()).detail; msg = typeof d === "string" ? d : JSON.stringify(d); } catch {}
      throw new ApiError(msg || "Request failed", res.status);
    }
    return (res.status === 204 ? null : await res.json()) as T;
  }, [call]);

  return { call, json };
}
