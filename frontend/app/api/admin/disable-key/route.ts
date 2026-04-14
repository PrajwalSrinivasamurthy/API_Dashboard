import { NextResponse } from "next/server";

import { backendAdminFetch, backendConfigured } from "@/lib/server-backend";

export async function POST(request: Request) {
  if (!backendConfigured()) {
    return NextResponse.json(
      { detail: "Server missing BACKEND_URL or ADMIN_API_KEY" },
      { status: 503 }
    );
  }
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON" }, { status: 400 });
  }
  try {
    const r = await backendAdminFetch("/admin/disable-key", {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (r.status === 204) {
      return new NextResponse(null, { status: 204 });
    }
    const text = await r.text();
    return new NextResponse(text, {
      status: r.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    return NextResponse.json(
      { detail: e instanceof Error ? e.message : "Upstream error" },
      { status: 502 }
    );
  }
}
