import { NextResponse } from "next/server";

import { DASHBOARD_TOKEN_COOKIE } from "@/lib/auth-cookie";
import { sessionCookieSecure } from "@/lib/session-cookie";

export async function POST(req: Request) {
  const base = process.env.BACKEND_URL?.trim().replace(/\/$/, "");
  if (!base) {
    return NextResponse.json({ detail: "BACKEND_URL not set" }, { status: 503 });
  }
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON" }, { status: 400 });
  }
  const r = await fetch(`${base}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const text = await r.text();
  if (!r.ok) {
    return new NextResponse(text || JSON.stringify({ detail: "Login failed" }), {
      status: r.status,
      headers: { "Content-Type": "application/json" },
    });
  }
  let data: { access_token?: string };
  try {
    data = JSON.parse(text) as { access_token?: string };
  } catch {
    return NextResponse.json({ detail: "Bad response from server" }, { status: 502 });
  }
  if (!data.access_token) {
    return NextResponse.json({ detail: "Bad response from server" }, { status: 502 });
  }
  const jwtHours = Number(process.env.JWT_EXPIRE_HOURS?.trim() || "5");
  const maxAge = Math.max(300, Math.round((Number.isFinite(jwtHours) ? jwtHours : 5) * 3600));

  const res = NextResponse.json({ ok: true });
  res.cookies.set(DASHBOARD_TOKEN_COOKIE, data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: sessionCookieSecure(req),
    maxAge,
  });
  return res;
}
