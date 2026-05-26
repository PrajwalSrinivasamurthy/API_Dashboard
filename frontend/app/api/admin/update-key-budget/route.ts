import { NextRequest, NextResponse } from "next/server";

import { backendAdminFetch, backendConfigured } from "@/lib/server-backend";

export async function POST(req: NextRequest) {
  if (!backendConfigured()) {
    return NextResponse.json(
      { detail: "Server missing BACKEND_URL or ADMIN_API_KEY" },
      { status: 503 }
    );
  }
  try {
    const body = await req.text();
    const r = await backendAdminFetch("/admin/update-key-budget", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
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
