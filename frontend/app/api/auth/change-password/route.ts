import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { DASHBOARD_TOKEN_COOKIE } from "@/lib/auth-cookie";

export async function POST(req: Request) {
  const token = cookies().get(DASHBOARD_TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
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
  const r = await fetch(`${base}/auth/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (r.status === 204) {
    return new NextResponse(null, { status: 204 });
  }
  const text = await r.text();
  return new NextResponse(text || JSON.stringify({ detail: "Change failed" }), {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}
