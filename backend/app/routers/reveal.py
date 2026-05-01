"""Public one-time virtual key reveal (no auth)."""

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.client_ip import get_client_ip
from app.config import get_settings
from app.database import get_db
from app.models import ProjectKey, ProjectKeyReveal
from app.schemas import RevealVirtualKeyResponse
from app.services.audit_log import log_audit
from app.services.teams_webhook import post_teams_text

router = APIRouter(prefix="/public", tags=["public"])


async def _notify_vk_reveal_failure(
    request: Request,
    *,
    reason: str,
    project_key_id: Optional[int] = None,
) -> None:
    s = get_settings()
    if not (s.teams_webhook_url or "").strip() or not s.teams_notify_vk_reveal_failure:
        return
    ip = get_client_ip(request) or "unknown"
    pk = f" Related project key id **{project_key_id}**." if project_key_id is not None else ""
    await post_teams_text(
        f"**Virtual key reveal failed** — {reason}. Client IP: **{ip}**.{pk} "
        "(Token value is never included in alerts.)"
    )


@router.get("/vk/{token}", response_model=RevealVirtualKeyResponse)
async def reveal_virtual_key(
    request: Request,
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    settings = get_settings()
    vk_teams = bool(
        (settings.teams_webhook_url or "").strip()
        and settings.teams_notify_vk_reveal_failure
    )

    t = (token or "").strip()
    if len(t) < 16:
        if vk_teams:
            await _notify_vk_reveal_failure(
                request, reason="invalid_token_format (too short or malformed)"
            )
        log_audit(
            "vk.reveal",
            outcome="not_found",
            request=request,
            extra={
                "path": "/public/vk/<redacted>",
                "http_status": 404,
                **({"teams_notification_sent": True} if vk_teams else {}),
            },
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    now = datetime.now(timezone.utc)
    res = await session.execute(
        select(ProjectKeyReveal)
        .where(ProjectKeyReveal.token == t)
        .with_for_update()
    )
    reveal = res.scalar_one_or_none()
    if reveal is None:
        if vk_teams:
            await _notify_vk_reveal_failure(
                request, reason="unknown_or_expired_reveal_token"
            )
        log_audit(
            "vk.reveal",
            outcome="not_found",
            request=request,
            extra={
                "path": "/public/vk/<redacted>",
                "http_status": 404,
                **({"teams_notification_sent": True} if vk_teams else {}),
            },
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if reveal.consumed_at is not None or reveal.expires_at <= now:
        if vk_teams:
            await _notify_vk_reveal_failure(
                request,
                reason="reveal_link_already_used_or_expired",
                project_key_id=reveal.project_key_id,
            )
        log_audit(
            "vk.reveal",
            outcome="not_found",
            request=request,
            extra={
                "path": "/public/vk/<redacted>",
                "http_status": 404,
                "project_key_id": reveal.project_key_id,
                **({"teams_notification_sent": True} if vk_teams else {}),
            },
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    pk_res = await session.execute(select(ProjectKey).where(ProjectKey.id == reveal.project_key_id))
    pk = pk_res.scalar_one_or_none()
    if pk is None:
        if vk_teams:
            await _notify_vk_reveal_failure(
                request,
                reason="project_key_missing_for_reveal_row",
                project_key_id=reveal.project_key_id,
            )
        log_audit(
            "vk.reveal",
            outcome="not_found",
            request=request,
            extra={
                "path": "/public/vk/<redacted>",
                "http_status": 404,
                "project_key_id": reveal.project_key_id,
                **({"teams_notification_sent": True} if vk_teams else {}),
            },
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    reveal.consumed_at = now
    client_ip = get_client_ip(request)
    if client_ip:
        pk.allowed_client_ip = client_ip
    log_audit(
        "vk.reveal",
        outcome="ok",
        request=request,
        extra={
            "path": "/public/vk/<redacted>",
            "http_status": 200,
            "project_key_id": pk.id,
            "project_key_name": pk.name,
            "bound_client_ip": client_ip,
        },
    )
    return RevealVirtualKeyResponse(key=pk.key)
