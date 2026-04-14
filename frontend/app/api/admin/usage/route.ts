import { NextResponse } from "next/server";

import { backendAdminFetch, backendConfigured } from "@/lib/server-backend";

export async function GET() {
  if (!backendConfigured()) {
    return NextResponse.json(
      { detail: "Server missing BACKEND_URL or ADMIN_API_KEY" },
      { status: 503 }
    );
  }
  try {
    const r = await backendAdminFetch("/admin/usage");
    const body = await r.text();
    return new NextResponse(body, {
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
