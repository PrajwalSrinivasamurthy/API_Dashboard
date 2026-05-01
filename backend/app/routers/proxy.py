"""POST /v1/chat/completions → OpenAI Chat Completions API (proxied)."""

import hashlib
import json
import logging
import time
from typing import Annotated, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_project_key_id_from_middleware
from app.models import ProjectKey, UsageLog
from app.services.pricing import estimate_cost_usd

logger = logging.getLogger(__name__)
router = APIRouter(tags=["proxy"])


def _normalize_upstream_error(data: object) -> dict:
    # Some upstream error payloads arrive as a one-element list; clients expect `{ "error": … }`.
    if isinstance(data, list) and data and isinstance(data[0], dict):
        first = data[0]
        if "error" in first:
            return first
        return {"error": {"message": json.dumps(first)[:2000]}}
    if isinstance(data, dict):
        if "error" in data:
            return data
        return {"error": {"message": json.dumps(data)[:2000]}}
    return {"error": {"message": str(data)[:2000]}}


def _as_sse_line(obj: dict) -> bytes:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")


_OPENAI_TOOL_CALL_ID_MAX = 64


def _short_tool_call_id(raw: str, memo: dict[str, str]) -> str:
    """OpenAI rejects tool_calls[].id longer than 64 chars; some clients send huge ids."""
    if len(raw) <= _OPENAI_TOOL_CALL_ID_MAX:
        return raw
    if raw not in memo:
        memo[raw] = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return memo[raw]


def _sanitize_openai_tool_call_ids(
    payload: object, memo: Optional[Dict[str, str]] = None
) -> None:
    """
    OpenAI requires tool_calls[].id and tool messages' tool_call_id length <= 64.
    Continue sometimes sends 400+ char ids. Walk the whole request JSON so we never miss
    a shape (odd role values, nested copies, etc.).
    """
    if memo is None:
        memo = {}

    if isinstance(payload, dict):
        tcid = payload.get("tool_call_id")
        if isinstance(tcid, str):
            payload["tool_call_id"] = _short_tool_call_id(tcid, memo)
        tcalls = payload.get("tool_calls")
        if isinstance(tcalls, list):
            for tc in tcalls:
                if isinstance(tc, dict):
                    tid = tc.get("id")
                    if isinstance(tid, str):
                        tc["id"] = _short_tool_call_id(tid, memo)
        for v in payload.values():
            _sanitize_openai_tool_call_ids(v, memo)
    elif isinstance(payload, list):
        for item in payload:
            _sanitize_openai_tool_call_ids(item, memo)


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    project_key_id: Annotated[int, Depends(get_project_key_id_from_middleware)],
):
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        payload = {}
    requested_stream = payload.get("stream") is True
    model = payload.get("model")
    model_name = model if isinstance(model, str) else None

    # Stability mode: many IDE clients stream by default, but stream transport
    # can be interrupted and produce cut responses. Convert to non-stream
    # upstream requests for reliability and consistent usage tracking.
    if requested_stream:
        payload["stream"] = False
    # OpenAI rejects stream_options unless stream is true (Continue may send both).
    if payload.get("stream") is not True:
        payload.pop("stream_options", None)

    _sanitize_openai_tool_call_ids(payload)
    body = json.dumps(payload).encode("utf-8")

    res = await session.execute(select(ProjectKey).where(ProjectKey.id == project_key_id))
    project_key = res.scalar_one_or_none()
    if project_key is None or not project_key.active:
        raise HTTPException(status_code=401, detail="Invalid or inactive project key")

    settings = get_settings()
    upstream = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    fwd = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": request.headers.get("content-type") or "application/json",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        try:
            r = await client.post(upstream, content=body, headers=fwd)
        except httpx.HTTPError as e:
            logger.exception("Upstream error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to reach OpenAI API",
            ) from e

        try:
            data = r.json()
        except json.JSONDecodeError:
            return JSONResponse(status_code=r.status_code, content={"error": {"message": r.text[:2000]}})

        status_code = r.status_code

    if status_code >= 400:
        return JSONResponse(status_code=status_code, content=_normalize_upstream_error(data))

    usage = data.get("usage") or {}
    pt = int(usage.get("prompt_tokens") or 0)
    ct = int(usage.get("completion_tokens") or 0)
    tt = int(usage.get("total_tokens") or (pt + ct))
    cost = estimate_cost_usd(model_name, pt, ct)

    session.add(
        UsageLog(
            project_key_id=project_key_id,
            prompt_tokens=pt,
            completion_tokens=ct,
            total_tokens=tt,
            cost=cost,
            model=model_name,
        )
    )
    project_key.used_tokens = int(project_key.used_tokens or 0) + tt

    if requested_stream:
        created = int(time.time())
        base_id = str(data.get("id") or f"chatcmpl-proxy-{created}")
        out_model = str(data.get("model") or model_name or "gpt-5")
        content = ""
        finish_reason = "stop"
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            msg = first.get("message") if isinstance(first.get("message"), dict) else {}
            content = str(msg.get("content") or "")
            finish_reason = str(first.get("finish_reason") or "stop")

        first_chunk = {
            "id": base_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": out_model,
            "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}
            ],
        }
        last_chunk = {
            "id": base_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": out_model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
        }

        async def one_shot_stream():
            yield _as_sse_line(first_chunk)
            yield _as_sse_line(last_chunk)
            yield b"data: [DONE]\n\n"

        return StreamingResponse(one_shot_stream(), media_type="text/event-stream")

    return JSONResponse(status_code=status_code, content=data)