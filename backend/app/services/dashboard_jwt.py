"""JWT for dashboard sessions (HS256)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

from app.config import get_settings


def create_dashboard_token(email: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=s.jwt_expire_hours)
    payload: Dict[str, Any] = {
        "sub": email,
        "typ": "dashboard",
        "iat": int(now.timestamp()),
        "exp": exp,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_dashboard_token(token: str) -> str:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise ValueError("Invalid token")
    if payload.get("typ") != "dashboard":
        raise ValueError("Invalid token type")
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise ValueError("Invalid subject")
    return sub
