import { NextResponse } from "next/server";

import { DASHBOARD_TOKEN_COOKIE } from "@/lib/auth-cookie";
import { sessionCookieSecure } from "@/lib/session-cookie";

export async function POST(req: Request) {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(DASHBOARD_TOKEN_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: sessionCookieSecure(req),
    maxAge: 0,
  });
  return res;
}
