import { describe, expect, it } from "vitest";

import { csrfMiddleware, problemMessage, readCookie } from "@/lib/api/client";
import { safeNext } from "@/components/auth-form";

describe("readCookie", () => {
  it("finds a cookie among others and decodes it", () => {
    expect(readCookie("cp_csrf", "a=1; cp_csrf=abc%3D%3D; b=2")).toBe("abc==");
    expect(readCookie("missing", "a=1")).toBeNull();
  });
});

describe("csrfMiddleware", () => {
  const run = (method: string) => {
    document.cookie = "cp_csrf=token123";
    const request = new Request("http://localhost/api/v1/me", { method });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (csrfMiddleware.onRequest as any)({ request }) as Request;
  };
  it("adds the header on unsafe methods only", () => {
    expect(run("PATCH").headers.get("X-CSRF-Token")).toBe("token123");
    expect(run("GET").headers.get("X-CSRF-Token")).toBeNull();
  });
});

describe("problemMessage", () => {
  it("prefers the first validation error with its field", () => {
    const problem = { title: "Validation error", errors: [{ loc: ["body", "email"], msg: "not a valid email", type: "x" }] };
    expect(problemMessage(problem)).toBe("email: not a valid email");
  });
  it("falls back to detail, then title", () => {
    expect(problemMessage({ title: "Password too weak", detail: "Password: at least 12 characters" })).toBe(
      "Password: at least 12 characters",
    );
    expect(problemMessage({ title: "Invalid email or password" })).toBe("Invalid email or password");
    expect(problemMessage(undefined)).toBe("Something went wrong");
  });
});

describe("safeNext", () => {
  it("only allows same-site relative paths", () => {
    expect(safeNext("/dashboard/tests")).toBe("/dashboard/tests");
    expect(safeNext("//evil.example")).toBe("/dashboard");
    expect(safeNext("https://evil.example")).toBe("/dashboard");
    expect(safeNext(null)).toBe("/dashboard");
  });
});
