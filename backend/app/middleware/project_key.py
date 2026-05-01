"""Validate x-project-key for POST /v1/chat/completions."""

from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from sqlalchemy import select

from app.database import async_session_factory
from app.models import ProjectKey


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


class ProjectKeyValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method != "POST" or request.url.path.rstrip("/") != "/v1/chat/completions":
            return await call_next(request)

        raw = _extract_project_key(request)
        if not raw:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Missing project key: use x-project-key or Authorization: Bearer",
                    }
                },
            )

        async with async_session_factory() as session:
            result = await session.execute(select(ProjectKey).where(ProjectKey.key == raw))
            row = result.scalar_one_or_none()

        if row is None or not row.active:
            return JSONResponse(
                status_code=401,
                content={"error": {"message": "Invalid or inactive project key"}},
            )

        request.state.project_key_id = row.id
        request.state.project_key_name = row.name
        return await call_next(request)
