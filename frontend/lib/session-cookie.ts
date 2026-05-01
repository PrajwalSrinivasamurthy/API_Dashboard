/**
 * Set `Secure` on session cookies only when the incoming request is HTTPS
 * (including TLS terminated at a reverse proxy that sets X-Forwarded-Proto).
 * Using NODE_ENV === "production" alone breaks plain-HTTP deployments.
 */
export function sessionCookieSecure(req: Request): boolean {
  const forwarded = req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim();
  if (forwarded === "https") return true;
  if (forwarded === "http") return false;
  return process.env.COOKIE_SECURE === "true";
}
