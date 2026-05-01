"""Dashboard login and password change (whitelist in dashboard_users)."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
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
from app.services.dashboard_jwt import create_dashboard_token, decode_dashboard_token
from app.services.passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


def _normalize_email(raw: str) -> str:
    return raw.strip().lower()


@router.post("/login", response_model=DashboardTokenResponse)
async def login(body: DashboardLoginRequest, session: Annotated[AsyncSession, Depends(get_db)]):
    email = _normalize_email(body.email)
    result = await session.execute(select(DashboardUser).where(DashboardUser.email == email))
    row = result.scalar_one_or_none()
    if row is None or not verify_password(body.password, row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_dashboard_token(email)
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
    body: DashboardChangePasswordRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    email: Annotated[str, Depends(_dashboard_email_from_bearer)],
):
    result = await session.execute(select(DashboardUser).where(DashboardUser.email == email))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not verify_password(body.old_password, row.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    row.password_hash = hash_password(body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
