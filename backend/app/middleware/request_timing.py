"""Request timing middleware for all HTTP requests."""

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.client_ip import get_client_ip

logger = logging.getLogger("app.timing")


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "method=%s path=%s status=%s duration_ms=%.2f client_ip=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            get_client_ip(request) or "-",
        )
        return response
