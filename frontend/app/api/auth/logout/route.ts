import { NextResponse } from "next/server";

import { DASHBOARD_TOKEN_COOKIE } from "@/lib/auth-cookie";

export async function POST() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(DASHBOARD_TOKEN_COOKIE, "", {
    httpOnly: true,
    path: "/",
    maxAge: 0,
  });
  return res;
}
