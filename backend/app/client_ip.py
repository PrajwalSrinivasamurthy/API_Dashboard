"""Best-effort client IP from reverse-proxy headers or transport."""

from typing import Optional

from starlette.requests import Request


def get_client_ip(request: Request) -> Optional[str]:
    """Prefer X-Forwarded-For (first hop), then CF / Vercel / X-Real-IP, then TCP peer."""
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first[:45]
    cf = request.headers.get("cf-connecting-ip") or request.headers.get("CF-Connecting-IP")
    if cf and (ip := cf.strip()):
        return ip[:45]
    xri = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
    if xri and (ip := xri.strip()):
        return ip[:45]
    vercel = request.headers.get("x-vercel-forwarded-for")
    if vercel and (ip := vercel.split(",")[0].strip()):
        return ip[:45]
    client = request.client
    if client and client.host:
        return client.host[:45]
    return None
