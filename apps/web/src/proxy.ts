import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Optimistic redirect only: checks the session cookie exists. The API remains the authority and
 * every protected call is verified server-side (an expired cookie still gets a 401 there).
 */
const PROTECTED = ["/dashboard", "/coach", "/tests", "/attempts", "/analytics", "/companies", "/generate"];

export function proxy(request: NextRequest) {
  const hasSession = request.cookies.has("cp_session");
  const { pathname } = request.nextUrl;

  if (!hasSession && PROTECTED.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  if (hasSession && (pathname === "/login" || pathname === "/register")) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/tests/:path*",
    "/coach/:path*",
    "/attempts/:path*",
    "/analytics/:path*",
    "/companies/:path*",
    "/generate/:path*",
    "/login",
    "/register",
  ],
};
