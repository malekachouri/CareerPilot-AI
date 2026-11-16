import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type User = components["schemas"]["UserOut"];
export type SessionOut = components["schemas"]["SessionOut"];

/** RFC 9457 problem details returned by the API for every error. */
export type Problem = {
  type: string;
  title: string;
  status: number;
  detail?: string;
  errors?: { loc: (string | number)[]; msg: string; type: string }[];
};

const CSRF_COOKIE = "cp_csrf";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export function readCookie(name: string, cookieString: string = globalThis.document?.cookie ?? ""): string | null {
  for (const part of cookieString.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

/** Echo the CSRF cookie in a header on state-changing requests (double-submit, checked server-side). */
export const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    if (UNSAFE.has(request.method)) {
      const token = readCookie(CSRF_COOKIE);
      if (token) request.headers.set("X-CSRF-Token", token);
    }
    return request;
  },
};

// Same-origin: Next.js proxies /api/* to FastAPI (see next.config.ts).
export const api = createClient<paths>({ baseUrl: "", credentials: "same-origin" });
api.use(csrfMiddleware);

/** Human-readable message for a problem+json error (first validation message if any). */
export function problemMessage(error: unknown, fallback = "Something went wrong"): string {
  if (!error || typeof error !== "object") return fallback;
  const p = error as Partial<Problem> & { detail?: unknown };
  if (Array.isArray(p.errors) && p.errors.length > 0) {
    const first = p.errors[0];
    const field = first.loc.filter((l) => l !== "body").join(".");
    return field ? `${field}: ${first.msg}` : first.msg;
  }
  if (typeof p.detail === "string") return p.detail;
  return p.title ?? fallback;
}
