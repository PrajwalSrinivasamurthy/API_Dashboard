"""Admin APIs (X-Admin-Key)."""

import json
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import require_admin
from app.models import DashboardUser, ProjectKey, ProjectKeyReveal, UsageLog
from app.schemas import (
    AdminUpdateDashboardUserPasswordRequest,
    AdminUsageResponse,
    CreateDashboardUserRequest,
    CreateProjectKeyRequest,
    CreateProjectKeyResponse,
    DashboardUserListItem,
    DeleteDashboardUserRequest,
    DisableKeyRequest,
    ProjectKeyAdminItem,
    UsagePerProject,
)
from app.services.passwords import hash_password

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _new_key() -> str:
    return f"sk_proj_{secrets.token_urlsafe(32)}"


async def _json_object_body(request: Request) -> dict:
    raw = await request.body()
    if not raw or not raw.strip():
        raise HTTPException(status_code=400, detail="Empty body")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    return payload


@router.get("/project-keys", response_model=List[ProjectKeyAdminItem])
async def list_project_keys(session: Annotated[AsyncSession, Depends(get_db)]):
    result = await session.execute(select(ProjectKey).order_by(ProjectKey.id.desc()))
    rows = result.scalars().all()
    if not rows:
        return []
    pids = [r.id for r in rows]
    spent_q = (
        select(UsageLog.project_key_id, func.coalesce(func.sum(UsageLog.cost), 0))
        .where(UsageLog.project_key_id.in_(pids))
        .group_by(UsageLog.project_key_id)
    )
    spent_res = await session.execute(spent_q)
    spent_map = {pid: Decimal(str(s or 0)).quantize(Decimal("0.000001")) for pid, s in spent_res.all()}
    return [
        ProjectKeyAdminItem(
            id=r.id,
            name=r.name,
            active=r.active,
            used_tokens=int(r.used_tokens or 0),
            created_at=r.created_at,
            allowed_client_ip=r.allowed_client_ip,
            budget_usd=Decimal(str(r.budget_usd or 0)).quantize(Decimal("0.01")),
            spent_usd=spent_map.get(r.id, Decimal("0")),
        )
        for r in rows
    ]


@router.post("/create-key", response_model=CreateProjectKeyResponse)
async def create_key(
    body: CreateProjectKeyRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    raw = _new_key()
    row = ProjectKey(key=raw, name=body.name.strip(), active=True)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    ttl_hours = get_settings().jwt_expire_hours
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    reveal = ProjectKeyReveal(
        token=secrets.token_urlsafe(32),
        project_key_id=row.id,
        expires_at=expires_at,
    )
    session.add(reveal)
    await session.flush()
    return CreateProjectKeyResponse(
        id=row.id,
        name=row.name,
        active=row.active,
        reveal_token=reveal.token,
        reveal_expires_at=reveal.expires_at,
    )


@router.post("/disable-key", status_code=status.HTTP_204_NO_CONTENT)
async def disable_key(
    body: DisableKeyRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    if body.id is None and (body.key is None or not body.key.strip()):
        raise HTTPException(status_code=400, detail="Provide id or key")

    if body.id is not None:
        q = select(ProjectKey).where(ProjectKey.id == body.id)
    else:
        q = select(ProjectKey).where(ProjectKey.key == body.key.strip())
    result = await session.execute(q)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Project key not found")
    row.active = False
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/usage", response_model=AdminUsageResponse)
async def admin_usage(session: Annotated[AsyncSession, Depends(get_db)]):
    q = (
        select(
            ProjectKey.id,
            ProjectKey.name,
            func.coalesce(func.sum(UsageLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(UsageLog.cost), 0).label("total_cost"),
            func.max(UsageLog.created_at).label("last_used"),
        )
        .outerjoin(UsageLog, UsageLog.project_key_id == ProjectKey.id)
        .group_by(ProjectKey.id, ProjectKey.name)
        .order_by(ProjectKey.id)
    )
    result = await session.execute(q)
    rows = result.all()

    per_project: List[UsagePerProject] = []
    total_cost = Decimal("0")
    total_tokens = 0
    for r in rows:
        tokens = int(r.total_tokens or 0)
        cost = Decimal(str(r.total_cost or 0))
        total_tokens += tokens
        total_cost += cost
        per_project.append(
            UsagePerProject(
                project_key_id=r.id,
                project_name=r.name,
                total_tokens=tokens,
                total_cost=cost.quantize(Decimal("0.000001")),
                last_used=r.last_used,
            )
        )

    return AdminUsageResponse(
        per_project=per_project,
        total_cost=total_cost.quantize(Decimal("0.000001")),
        total_tokens=total_tokens,
    )


@router.get("/dashboard-users", response_model=List[DashboardUserListItem])
async def list_dashboard_users(session: Annotated[AsyncSession, Depends(get_db)]):
    result = await session.execute(select(DashboardUser).order_by(DashboardUser.id))
    rows = result.scalars().all()
    return [
        DashboardUserListItem(
            id=r.id,
            email=r.email,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.post("/dashboard-users", status_code=status.HTTP_201_CREATED)
async def create_dashboard_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    payload = await _json_object_body(request)
    body = CreateDashboardUserRequest.model_validate(payload)
    email = body.email.strip().lower()
    existing = await session.execute(select(DashboardUser).where(DashboardUser.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already whitelisted")
    row = DashboardUser(email=email, password_hash=hash_password(body.password))
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return {"id": row.id, "email": row.email}


@router.post("/delete-dashboard-user", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    payload = await _json_object_body(request)
    body = DeleteDashboardUserRequest.model_validate(payload)
    if body.id is not None:
        q = select(DashboardUser).where(DashboardUser.id == body.id)
    else:
        q = select(DashboardUser).where(DashboardUser.email == body.email.strip().lower())
    result = await session.execute(q)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Dashboard user not found")
    await session.delete(row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/update-dashboard-user-password", status_code=status.HTTP_204_NO_CONTENT)
async def update_dashboard_user_password(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    payload = await _json_object_body(request)
    body = AdminUpdateDashboardUserPasswordRequest.model_validate(payload)
    if body.id is not None:
        q = select(DashboardUser).where(DashboardUser.id == body.id)
    else:
        q = select(DashboardUser).where(DashboardUser.email == body.email.strip().lower())
    result = await session.execute(q)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Dashboard user not found")
    row.password_hash = hash_password(body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
