"""Microsoft Teams Incoming Webhook (optional)."""

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def post_teams_text(text: str) -> None:
    url = (get_settings().teams_webhook_url or "").strip()
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(url, json={"text": text})
            if r.status_code >= 400:
                logger.warning("Teams webhook HTTP %s: %s", r.status_code, r.text[:500])
    except Exception:
        logger.exception("Teams webhook request failed")
