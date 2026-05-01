"""Append-only JSON audit lines for IT (``app.audit`` → ``logs/audit.log``)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from starlette.requests import Request

from app.client_ip import get_client_ip

_logger = logging.getLogger("app.audit")


def log_audit(
    action: str,
    *,
    outcome: str = "ok",
    actor: Optional[str] = None,
    request: Optional[Request] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    One JSON object per line. Do not put secrets (API keys, raw project keys, passwords) in ``extra``.
    """
    row: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "channel": "audit",
        "action": action,
        "outcome": outcome,
    }
    if actor is not None:
        row["actor"] = actor
    if request is not None:
        row["client_ip"] = get_client_ip(request) or None
        row["method"] = request.method
        row["path"] = request.url.path
    if extra:
        for k, v in extra.items():
            if v is not None:
                row[k] = v
    _logger.info(json.dumps(row, ensure_ascii=False, default=str))
