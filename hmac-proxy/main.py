"""Forward ``POST /v1/chat/completions`` to the backend with HMAC headers added."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
HMAC_SIGNING_SECRET = (os.environ.get("HMAC_SIGNING_SECRET") or "").strip()
# Comma-separated origins, or * (default) for local dev
CORS_ORIGINS_RAW = (os.environ.get("CORS_ORIGINS") or "*").strip()

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def _extract_project_key(request: Request) -> Optional[str]:
    h = request.headers.get("x-project-key")
    if h and h.strip():
        return h.strip()
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


def _build_signing_payload(
    *, method: str, path: str, timestamp: str, nonce: str, body: bytes
) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    return "\n".join([method.upper(), path, timestamp, nonce, body_hash])


def _hmac_signature(secret: str, project_key: str, payload: str) -> str:
    key = f"{secret}:{project_key}".encode("utf-8")
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _forward_header_items(request: Request) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in request.headers.items():
        lk = k.lower()
        if lk in HOP_BY_HOP or lk.startswith("x-forwarded-"):
            continue
        if lk in ("x-signature", "x-timestamp", "x-nonce"):
            continue
        out[k] = v
    return out


def _cors_config() -> tuple[list[str], bool]:
    if CORS_ORIGINS_RAW == "*":
        return (["*"], False)
    parts = [p.strip() for p in CORS_ORIGINS_RAW.split(",") if p.strip()]
    return (parts if parts else ["*"], True)


app = FastAPI(title="HMAC gateway", version="1.0.0")
_origins, _creds = _cors_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "role": "hmac-proxy", "backend": BACKEND_URL}


@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request):
    if not HMAC_SIGNING_SECRET:
        return Response(
            content='{"error":{"message":"HMAC_SIGNING_SECRET is not set on the proxy"}}',
            status_code=500,
            media_type="application/json",
        )

    body = await request.body()
    project_key = _extract_project_key(request)
    if not project_key:
        return Response(
            content='{"error":{"message":"Missing project key: use x-project-key or Authorization: Bearer"}}',
            status_code=401,
            media_type="application/json",
        )

    path = "/v1/chat/completions"
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    payload = _build_signing_payload(
        method="POST",
        path=path,
        timestamp=ts,
        nonce=nonce,
        body=body,
    )
    sig = _hmac_signature(HMAC_SIGNING_SECRET, project_key, payload)

    forward_headers = _forward_header_items(request)
    forward_headers["x-signature"] = sig
    forward_headers["x-timestamp"] = ts
    forward_headers["x-nonce"] = nonce

    url = f"{BACKEND_URL}{path}"
    timeout = httpx.Timeout(600.0, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=forward_headers, content=body)

    out_headers = {
        k: v
        for k, v in r.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "content-length"
    }
    return Response(
        content=r.content,
        status_code=r.status_code,
        headers=out_headers,
    )
