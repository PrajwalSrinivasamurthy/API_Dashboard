"""POST /v1/chat/completions → OpenAI Chat Completions API (proxied)."""

import hashlib
import json
import logging
import time
from decimal import Decimal
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.client_ip import get_client_ip
from app.config import get_settings
from app.database import get_db
from app.deps import get_project_key_id_from_middleware
from app.models import ProjectKey, ProjectKeySecurityEvent, UsageLog
from app.services.audit_log import log_audit
from app.services.pricing import estimate_cost_usd
from app.services.teams_webhook import post_teams_text
from app.services.usage_limits import (
    total_spent_usd,
    upper_bound_request_cost_usd,
    upper_bound_request_tokens,
    window_usage_stats,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["proxy"])


def _normalize_upstream_error(data: object) -> dict:
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
    """OpenAI rejects tool call IDs longer than 64 chars."""
    if len(raw) <= _OPENAI_TOOL_CALL_ID_MAX:
        return raw
    if raw not in memo:
        memo[raw] = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return memo[raw]


def _sanitize_openai_tool_call_ids(
    payload: object, memo: dict[str, str] | None = None
) -> None:
    """Ensure tool call IDs are <= 64 chars across the full payload."""
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

    if requested_stream:
        payload["stream"] = False
    if payload.get("stream") is not True:
        payload.pop("stream_options", None)

    _sanitize_openai_tool_call_ids(payload)
    body = json.dumps(payload).encode("utf-8")

    res = await session.execute(select(ProjectKey).where(ProjectKey.id == project_key_id))
    project_key = res.scalar_one_or_none()
    if project_key is None or not project_key.active:
        raise HTTPException(status_code=401, detail="Invalid or inactive project key")

    settings = get_settings()
    client_ip = (get_client_ip(request) or "").strip() or None
    budget_cap = Decimal(str(project_key.budget_usd or 0)).quantize(Decimal("0.01"))
    spent_prior = await total_spent_usd(session, project_key_id)
    upper_cost = upper_bound_request_cost_usd(model_name, payload)

    if spent_prior + upper_cost > budget_cap:
        session.add(
            ProjectKeySecurityEvent(
                project_key_id=project_key_id,
                event_type="budget_blocked",
                client_ip=client_ip,
                detail=f"spent={spent_prior}; est_max={upper_cost}; cap={budget_cap}"[:2000],
            )
        )
        budget_blocked_extra: dict = {
            "http_status": 402,
            "project_key_id": project_key_id,
            "project_key_name": project_key.name,
            "spent_usd": str(spent_prior),
            "budget_cap_usd": str(budget_cap),
        }
        if (
            (settings.teams_webhook_url or "").strip()
            and settings.teams_notify_budget_blocked
        ):
            await post_teams_text(
                f"**Budget cap blocked** a request for key **{project_key.name}** (id {project_key_id}).\n"
                f"Approx spend before this request: **{spent_prior}** USD; cap: **{budget_cap}** USD.\n"
                f"Client IP: **{client_ip or 'unknown'}**."
            )
            budget_blocked_extra["teams_notification_sent"] = True
        log_audit(
            "proxy.budget_blocked",
            outcome="denied",
            request=request,
            extra=budget_blocked_extra,
        )
        return JSONResponse(
            status_code=402,
            content={
                "error": {
                    "message": f"Project key budget cap reached (${budget_cap}).",
                }
            },
        )

    win_sec = settings.spike_window_seconds
    w_cnt, w_cost, w_toks = await window_usage_stats(session, project_key_id, win_sec)
    upper_toks = upper_bound_request_tokens(payload)
    spike_cost_cap = Decimal(str(settings.spike_max_cost_usd)).quantize(Decimal("0.000001"))

    spike_detail = None
    if w_cnt >= settings.spike_max_requests:
        spike_detail = f"requests_in_{win_sec}s={w_cnt}; max={settings.spike_max_requests}"
    elif w_cost + upper_cost > spike_cost_cap:
        spike_detail = f"cost_in_window={w_cost}; est_add={upper_cost}; max={spike_cost_cap}"
    elif w_toks + upper_toks > settings.spike_max_tokens:
        spike_detail = f"tokens_in_window={w_toks}; est_add={upper_toks}; max={settings.spike_max_tokens}"

    if spike_detail:
        session.add(
            ProjectKeySecurityEvent(
                project_key_id=project_key_id,
                event_type="spike_blocked",
                client_ip=client_ip,
                detail=spike_detail[:2000],
            )
        )
        spike_blocked_extra: dict = {
            "http_status": 429,
            "project_key_id": project_key_id,
            "project_key_name": project_key.name,
            "detail": spike_detail[:500] if spike_detail else None,
        }
        if (
            (settings.teams_webhook_url or "").strip()
            and settings.teams_notify_spike_blocked
        ):
            detail_short = (spike_detail or "")[:400]
            await post_teams_text(
                f"**Spike limit blocked** a request for key **{project_key.name}** (id {project_key_id}).\n"
                f"Detail: {detail_short}\n"
                f"Client IP: **{client_ip or 'unknown'}**."
            )
            spike_blocked_extra["teams_notification_sent"] = True
        log_audit(
            "proxy.spike_blocked",
            outcome="denied",
            request=request,
            extra=spike_blocked_extra,
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": "Spike limit exceeded for this project key. Retry later.",
                }
            },
        )

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

    await session.flush()
    spent_after = await total_spent_usd(session, project_key_id)
    frac = Decimal(str(settings.budget_threshold_fraction))
    threshold_amt = (budget_cap * frac).quantize(Decimal("0.01"))
    if spent_after >= threshold_amt and not project_key.budget_warn_sent:
        session.add(
            ProjectKeySecurityEvent(
                project_key_id=project_key_id,
                event_type="budget_threshold",
                client_ip=client_ip,
                detail=f"spent={spent_after}; threshold={threshold_amt}; cap={budget_cap}"[:2000],
            )
        )
        project_key.budget_warn_sent = True
        pct = float(settings.budget_threshold_fraction) * 100.0
        threshold_extra: dict = {
            "project_key_id": project_key_id,
            "project_key_name": project_key.name,
            "spent_usd": str(spent_after),
            "threshold_usd": str(threshold_amt),
            "budget_cap_usd": str(budget_cap),
        }
        if (
            (settings.teams_webhook_url or "").strip()
            and settings.teams_notify_budget_threshold
        ):
            await post_teams_text(
                f"Budget threshold ({pct:.0f}%) reached for key **{project_key.name}** (id {project_key_id}): "
                f"~{spent_after} USD spent of {budget_cap} USD cap."
            )
            threshold_extra["teams_notification_sent"] = True
        log_audit(
            "proxy.budget_threshold",
            outcome="warn",
            request=request,
            extra=threshold_extra,
        )

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