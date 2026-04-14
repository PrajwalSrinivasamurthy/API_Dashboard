/**
 * Server-only: call FastAPI admin routes with X-Admin-Key.
 * Never import this from client components.
 */

function requireEnv(): { base: string; adminKey: string } {
  const base = process.env.BACKEND_URL?.trim().replace(/\/$/, "");
  const adminKey = process.env.ADMIN_API_KEY?.trim();
  if (!base || !adminKey) {
    throw new Error("BACKEND_URL and ADMIN_API_KEY must be set in the Next.js environment");
  }
  return { base, adminKey };
}

export async function backendAdminFetch(
  path: string,
  init?: RequestInit
): Promise<Response> {
  const { base, adminKey } = requireEnv();
  const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
  return fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": adminKey,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
}

export function backendConfigured(): boolean {
  return Boolean(process.env.BACKEND_URL?.trim() && process.env.ADMIN_API_KEY?.trim());
}

/** Dashboard needs JWT_SECRET (same as backend) for login cookies and middleware. */
export function dashboardEnvReady(): boolean {
  return Boolean(
    process.env.BACKEND_URL?.trim() &&
      process.env.ADMIN_API_KEY?.trim() &&
      process.env.JWT_SECRET?.trim()
  );
}
