"""Validate project key auth for POST /v1/chat/completions."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.client_ip import get_client_ip
from app.config import get_settings
from app.database import async_session_factory
from app.models import HmacNonce, ProjectKey, ProjectKeySecurityEvent
from app.services.audit_log import log_audit
from app.services.teams_webhook import post_teams_text


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


async def _notify_hmac_failure(*, project_key_id: int, project_key_name: str, reason: str, client_ip: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    msg = (
        f"Security alert for project key **{project_key_name}** (id {project_key_id}). "
        f"HMAC validation failed (**{reason}**) at {now}. "
        f"Client IP: **{client_ip or 'unknown'}**. "
        "Review usage/security events and disable this virtual key if suspicious."
    )
    await post_teams_text(msg)


class ProjectKeyValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method != "POST" or request.url.path.rstrip("/") != "/v1/chat/completions":
            return await call_next(request)

        settings = get_settings()
        raw = _extract_project_key(request)
        if not raw:
            log_audit(
                "proxy.project_key_missing",
                outcome="denied",
                request=request,
                extra={"http_status": 401},
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Missing project key: use x-project-key or Authorization: Bearer",
                    }
                },
            )

        body = await request.body()

        async with async_session_factory() as session:
            result = await session.execute(select(ProjectKey).where(ProjectKey.key == raw))
            row = result.scalar_one_or_none()

        if row is None or not row.active:
            log_audit(
                "proxy.project_key_invalid",
                outcome="denied",
                request=request,
                extra={"http_status": 401},
            )
            return JSONResponse(
                status_code=401,
                content={"error": {"message": "Invalid or inactive project key"}},
            )

        current = (get_client_ip(request) or "").strip()

        if settings.enable_hmac_check:
            sig = (request.headers.get("x-signature") or "").strip().lower()
            ts_raw = (request.headers.get("x-timestamp") or "").strip()
            nonce = (request.headers.get("x-nonce") or "").strip()
            if not sig or not ts_raw or not nonce:
                await _notify_hmac_failure(
                    project_key_id=row.id,
                    project_key_name=row.name,
                    reason="missing_headers",
                    client_ip=current,
                )
                log_audit(
                    "proxy.hmac_missing",
                    outcome="denied",
                    request=request,
                    extra={"http_status": 401, "project_key_id": row.id},
                )
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "message": "Missing HMAC headers: x-signature, x-timestamp, x-nonce",
                        }
                    },
                )

            secret = (settings.hmac_signing_secret or "").strip()
            if not secret:
                log_audit(
                    "proxy.hmac_misconfigured",
                    outcome="denied",
                    request=request,
                    extra={"http_status": 500, "project_key_id": row.id},
                )
                return JSONResponse(
                    status_code=500,
                    content={"error": {"message": "HMAC is enabled but HMAC_SIGNING_SECRET is not set"}},
                )

            try:
                ts = int(ts_raw)
            except ValueError:
                ts = 0
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if ts <= 0 or abs(now_ts - ts) > max(1, int(settings.hmac_max_skew_seconds)):
                async with async_session_factory() as sec_session:
                    sec_session.add(
                        ProjectKeySecurityEvent(
                            project_key_id=row.id,
                            event_type="hmac_timestamp_invalid",
                            client_ip=current or None,
                            detail=f"timestamp={ts_raw}; skew={abs(now_ts - ts)}"[:2000],
                        )
                    )
                    await sec_session.commit()
                await _notify_hmac_failure(
                    project_key_id=row.id,
                    project_key_name=row.name,
                    reason="invalid_timestamp",
                    client_ip=current,
                )
                log_audit(
                    "proxy.hmac_timestamp_invalid",
                    outcome="denied",
                    request=request,
                    extra={"http_status": 401, "project_key_id": row.id},
                )
                return JSONResponse(
                    status_code=401,
                    content={"error": {"message": "Invalid or expired HMAC timestamp"}},
                )

            payload = _build_signing_payload(
                method=request.method,
                path=request.url.path,
                timestamp=ts_raw,
                nonce=nonce,
                body=body,
            )
            expected_sig = _hmac_signature(secret, row.key, payload)
            if not hmac.compare_digest(sig, expected_sig):
                async with async_session_factory() as sec_session:
                    sec_session.add(
                        ProjectKeySecurityEvent(
                            project_key_id=row.id,
                            event_type="hmac_signature_invalid",
                            client_ip=current or None,
                            detail=f"nonce={nonce[:128]}"[:2000],
                        )
                    )
                    await sec_session.commit()
                await _notify_hmac_failure(
                    project_key_id=row.id,
                    project_key_name=row.name,
                    reason="invalid_signature",
                    client_ip=current,
                )
                log_audit(
                    "proxy.hmac_signature_invalid",
                    outcome="denied",
                    request=request,
                    extra={"http_status": 401, "project_key_id": row.id},
                )
                return JSONResponse(
                    status_code=401,
                    content={"error": {"message": "Invalid HMAC signature"}},
                )

            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=max(1, int(settings.hmac_nonce_ttl_seconds)))
            async with async_session_factory() as nonce_session:
                await nonce_session.execute(delete(HmacNonce).where(HmacNonce.expires_at < now))
                existing = await nonce_session.execute(
                    select(HmacNonce).where(
                        HmacNonce.project_key_id == row.id,
                        HmacNonce.nonce == nonce,
                        HmacNonce.expires_at >= now,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    nonce_session.add(
                        ProjectKeySecurityEvent(
                            project_key_id=row.id,
                            event_type="hmac_replay_blocked",
                            client_ip=current or None,
                            detail=f"nonce={nonce[:128]}"[:2000],
                        )
                    )
                    await nonce_session.commit()
                    await _notify_hmac_failure(
                        project_key_id=row.id,
                        project_key_name=row.name,
                        reason="replay_detected",
                        client_ip=current,
                    )
                    log_audit(
                        "proxy.hmac_replay_blocked",
                        outcome="denied",
                        request=request,
                        extra={"http_status": 401, "project_key_id": row.id},
                    )
                    return JSONResponse(
                        status_code=401,
                        content={"error": {"message": "Replay detected (nonce already used)"}},
                    )
                nonce_session.add(HmacNonce(project_key_id=row.id, nonce=nonce[:128], expires_at=expires_at))
                try:
                    await nonce_session.commit()
                except IntegrityError:
                    await nonce_session.rollback()
                    nonce_session.add(
                        ProjectKeySecurityEvent(
                            project_key_id=row.id,
                            event_type="hmac_replay_blocked",
                            client_ip=current or None,
                            detail=f"nonce={nonce[:128]}"[:2000],
                        )
                    )
                    await nonce_session.commit()
                    await _notify_hmac_failure(
                        project_key_id=row.id,
                        project_key_name=row.name,
                        reason="replay_detected",
                        client_ip=current,
                    )
                    log_audit(
                        "proxy.hmac_replay_blocked",
                        outcome="denied",
                        request=request,
                        extra={"http_status": 401, "project_key_id": row.id},
                    )
                    return JSONResponse(
                        status_code=401,
                        content={"error": {"message": "Replay detected (nonce already used)"}},
                    )

        bound = (row.allowed_client_ip or "").strip()
        if settings.enable_ip_check and bound:
            current = (get_client_ip(request) or "").strip()
            if not current or current != bound:
                now = datetime.now(timezone.utc)
                detail = f"expected_ip={bound}; client_ip={current or 'none'}"
                async with async_session_factory() as sec_session:
                    sec_session.add(
                        ProjectKeySecurityEvent(
                            project_key_id=row.id,
                            event_type="ip_mismatch",
                            client_ip=current or None,
                            detail=detail[:2000],
                        )
                    )
                    await sec_session.commit()
                msg = (
                    f"Unidentified login for key **{row.name}** at {now.isoformat()} "
                    f"from IP **{current or 'unknown'}** (expected **{bound}**)."
                )
                await post_teams_text(msg)
                log_audit(
                    "proxy.ip_mismatch",
                    outcome="denied",
                    request=request,
                    extra={
                        "http_status": 403,
                        "project_key_id": row.id,
                        "project_key_name": row.name,
                        "client_ip_observed": current or None,
                        "allowed_client_ip": bound,
                    },
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "message": "This project key is bound to another IP address. "
                            "Use the same network as when you opened the reveal link.",
                        }
                    },
                )

        request.state.project_key_id = row.id
        request.state.project_key_name = row.name
        return await call_next(request)
