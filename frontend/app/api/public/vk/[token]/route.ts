import { NextResponse } from "next/server";

function backendBase(): string | null {
  const b = process.env.BACKEND_URL?.trim().replace(/\/$/, "");
  return b || null;
}

export async function GET(
  req: Request,
  context: { params: { token: string } }
) {
  const base = backendBase();
  if (!base) {
    return NextResponse.json({ detail: "BACKEND_URL not set" }, { status: 503 });
  }
  const token = context.params.token ?? "";
  const t = encodeURIComponent(token);

  const fwdHeaders: Record<string, string> = {};
  const xff = req.headers.get("x-forwarded-for");
  const xri = req.headers.get("x-real-ip");
  const vercel = req.headers.get("x-vercel-forwarded-for");
  const cf = req.headers.get("cf-connecting-ip");
  if (xff) fwdHeaders["X-Forwarded-For"] = xff;
  else if (vercel) fwdHeaders["X-Forwarded-For"] = vercel;
  else if (cf) fwdHeaders["CF-Connecting-IP"] = cf;
  else if (xri) fwdHeaders["X-Real-IP"] = xri;

  const r = await fetch(`${base}/public/vk/${t}`, {
    method: "GET",
    cache: "no-store",
    headers: fwdHeaders,
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}
