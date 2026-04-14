import { NextResponse, type NextRequest } from "next/server";
import { jwtVerify } from "jose";

import { DASHBOARD_TOKEN_COOKIE } from "@/lib/auth-cookie";

function getSecret(): Uint8Array | null {
  const raw = process.env.JWT_SECRET?.trim();
  if (!raw) return null;
  return new TextEncoder().encode(raw);
}

async function verifyToken(token: string, secret: Uint8Array): Promise<void> {
  const { payload } = await jwtVerify(token, secret, { algorithms: ["HS256"] });
  if (payload.typ !== "dashboard") throw new Error("wrong typ");
}

export async function middleware(req: NextRequest) {
  const secret = getSecret();
  const pathname = req.nextUrl.pathname;
  const token = req.cookies.get(DASHBOARD_TOKEN_COOKIE)?.value ?? null;

  if (!secret) {
    if (pathname.startsWith("/api/admin")) {
      return NextResponse.json(
        { detail: "Server missing JWT_SECRET" },
        { status: 503 }
      );
    }
    if (pathname.startsWith("/dashboard")) {
      const u = req.nextUrl.clone();
      u.pathname = "/login";
      u.searchParams.set("error", "config");
      return NextResponse.redirect(u);
    }
    return NextResponse.next();
  }

  if (pathname === "/login" || pathname.startsWith("/login/")) {
    if (token) {
      try {
        await verifyToken(token, secret);
        return NextResponse.redirect(new URL("/dashboard", req.url));
      } catch {
        const res = NextResponse.next();
        res.cookies.delete(DASHBOARD_TOKEN_COOKIE);
        return res;
      }
    }
    return NextResponse.next();
  }

  if (!token) {
    if (pathname.startsWith("/api/admin")) {
      return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
    }
    return NextResponse.redirect(new URL("/login", req.url));
  }

  try {
    await verifyToken(token, secret);
  } catch {
    if (pathname.startsWith("/api/admin")) {
      return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
    }
    const res = NextResponse.redirect(new URL("/login", req.url));
    res.cookies.delete(DASHBOARD_TOKEN_COOKIE);
    return res;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/api/admin/:path*", "/login"],
};
