import { problemMessage, readCookie } from "./client";

/** Small typed fetch helper for the coach endpoints (computed views, see coach-types.ts). */
export async function coach<T>(path: string, init?: { method?: string; body?: unknown }): Promise<{ data?: T; error?: string }> {
  const method = init?.method ?? "GET";
  const headers: Record<string, string> = {};
  if (init?.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = readCookie("cp_csrf") ?? "";
  const res = await fetch(`/api/v1${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: init?.body !== undefined ? JSON.stringify(init.body) : method !== "GET" ? "{}" : undefined,
  });
  const body = res.status === 204 ? undefined : await res.json().catch(() => undefined);
  if (!res.ok) return { error: problemMessage(body) };
  return { data: body as T };
}
