"""Public one-time virtual key reveal (no auth)."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.client_ip import get_client_ip
from app.database import get_db
from app.models import ProjectKey, ProjectKeyReveal
from app.schemas import RevealVirtualKeyResponse
from app.services.audit_log import log_audit

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/vk/{token}", response_model=RevealVirtualKeyResponse)
async def reveal_virtual_key(
    request: Request,
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    t = (token or "").strip()
    if len(t) < 16:
        log_audit(
            "vk.reveal",
            outcome="not_found",
            request=request,
            extra={"path": "/public/vk/<redacted>", "http_status": 404},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    now = datetime.now(timezone.utc)
    res = await session.execute(
        select(ProjectKeyReveal)
        .where(ProjectKeyReveal.token == t)
        .with_for_update()
    )
    reveal = res.scalar_one_or_none()
    if reveal is None or reveal.consumed_at is not None or reveal.expires_at <= now:
        log_audit(
            "vk.reveal",
            outcome="not_found",
            request=request,
            extra={"path": "/public/vk/<redacted>", "http_status": 404},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    pk_res = await session.execute(select(ProjectKey).where(ProjectKey.id == reveal.project_key_id))
    pk = pk_res.scalar_one_or_none()
    if pk is None:
        log_audit(
            "vk.reveal",
            outcome="not_found",
            request=request,
            extra={"path": "/public/vk/<redacted>", "http_status": 404},
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
