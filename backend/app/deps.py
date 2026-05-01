from typing import Optional

from fastapi import Header, HTTPException, Request, status

from app.config import get_settings


def require_admin(x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")) -> None:
    expected = get_settings().admin_api_key.strip()
    got = (x_admin_key or "").strip()
    if not got or got != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing admin key")


def get_project_key_id_from_middleware(request: Request) -> int:
    pk = getattr(request.state, "project_key_id", None)
    if pk is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Project key was not validated",
        )
    return int(pk)
