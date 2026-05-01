"""Microsoft Teams via webhook URL (Incoming Webhook or Power Automate HTTP trigger)."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def build_teams_adaptive_card(body_text: str) -> Dict[str, Any]:
    """Adaptive Card JSON for Power Automate / Teams 'Post card' actions."""
    s = get_settings()
    title = (s.teams_adaptive_card_title or "").strip() or "API Dashboard Alert"
    return {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": title,
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": "TextBlock",
                "text": body_text,
                "wrap": True,
            },
        ],
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
    }


async def post_teams_text(text: str) -> None:
    settings = get_settings()
    url = (settings.teams_webhook_url or "").strip()
    if not url:
        return
    if settings.teams_use_adaptive_card:
        payload: Dict[str, Any] = build_teams_adaptive_card(text)
    else:
        payload = {"text": text}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(url, json=payload)
            if r.status_code >= 400:
                logger.warning("Teams webhook HTTP %s: %s", r.status_code, r.text[:500])
    except Exception:
        logger.exception("Teams webhook request failed")
