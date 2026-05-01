"""Audit middleware: logs each completed ``/admin/*`` HTTP call."""

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.audit_log import log_audit


class AuditHttpMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
        path = request.url.path
        status = response.status_code

        if path.startswith("/admin"):
            log_audit(
                "admin.http",
                outcome="ok" if status < 400 else "error",
                request=request,
                extra={"http_status": status, "duration_ms": elapsed_ms},
            )

        return response
