import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DashboardUser
from app.schemas import (
    DashboardChangePasswordRequest,
    DashboardLoginRequest,
    DashboardTokenResponse,
)
from app.services.audit_log import log_audit
from app.services.dashboard_jwt import create_dashboard_token, decode_dashboard_token
from app.services.passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger("app.auth")


def _normalize_email(raw: str) -> str:
    return raw.strip().lower()


@router.post("/login", response_model=DashboardTokenResponse)
async def login(
    request: Request,
    body: DashboardLoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    email = _normalize_email(body.email)
    result = await session.execute(select(DashboardUser).where(DashboardUser.email == email))
    row = result.scalar_one_or_none()
    if row is None or not verify_password(body.password, row.password_hash):
        logger.warning("Dashboard login denied for email=%s", email)
        log_audit(
            "dashboard.login",
            outcome="denied",
            actor=email,
            request=request,
            extra={"http_status": 401},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_dashboard_token(email)
    logger.info("Dashboard login successful for email=%s", email)
    log_audit(
        "dashboard.login",
        outcome="ok",
        actor=email,
        request=request,
        extra={"http_status": 200},
    )
    return DashboardTokenResponse(access_token=token)


async def _dashboard_email_from_bearer(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
) -> str:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    try:
        return decode_dashboard_token(creds.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: Request,
    body: DashboardChangePasswordRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    email: Annotated[str, Depends(_dashboard_email_from_bearer)],
):
    result = await session.execute(select(DashboardUser).where(DashboardUser.email == email))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not verify_password(body.old_password, row.password_hash):
        logger.warning("Dashboard password change denied for email=%s", email)
        log_audit(
            "dashboard.change_password",
            outcome="denied",
            actor=email,
            request=request,
            extra={"http_status": 400, "reason": "old_password_mismatch"},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    row.password_hash = hash_password(body.new_password)
    logger.info("Dashboard password changed for email=%s", email)
    log_audit(
        "dashboard.change_password",
        outcome="ok",
        actor=email,
        request=request,
        extra={"http_status": 204},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
