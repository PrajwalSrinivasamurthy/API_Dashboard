"""Per-key budget and spike (rolling window) checks."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UsageLog
from app.services.pricing import estimate_cost_usd


def upper_bound_request_tokens(payload: Dict[str, Any]) -> int:
    """Conservative token ceiling for this request (spike gate)."""
    mt = payload.get("max_tokens") or payload.get("max_completion_tokens")
    try:
        comp = min(int(mt), 500_000) if mt is not None else 8192
    except (TypeError, ValueError):
        comp = 8192
    prompt = 128_000
    return prompt + comp


def upper_bound_request_cost_usd(model_name: Optional[str], payload: Dict[str, Any]) -> Decimal:
    """Conservative upper bound for this request before upstream (for budget gate)."""
    mt = payload.get("max_tokens") or payload.get("max_completion_tokens")
    try:
        comp_cap = min(int(mt), 500_000) if mt is not None else 8192
    except (TypeError, ValueError):
        comp_cap = 8192
    prompt_cap = 128_000
    return estimate_cost_usd(model_name, prompt_cap, comp_cap)


async def total_spent_usd(session: AsyncSession, project_key_id: int) -> Decimal:
    q = select(func.coalesce(func.sum(UsageLog.cost), 0)).where(UsageLog.project_key_id == project_key_id)
    r = await session.execute(q)
    v = r.scalar_one()
    return Decimal(str(v or 0)).quantize(Decimal("0.000001"))


async def window_usage_stats(
    session: AsyncSession, project_key_id: int, window_seconds: int
) -> Tuple[int, Decimal, int]:
    """Returns (request_count, sum_cost_usd, sum_total_tokens) in the rolling window."""
    start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    q = select(
        func.count(UsageLog.id),
        func.coalesce(func.sum(UsageLog.cost), 0),
        func.coalesce(func.sum(UsageLog.total_tokens), 0),
    ).where(UsageLog.project_key_id == project_key_id, UsageLog.created_at >= start)
    r = await session.execute(q)
    row = r.one()
    cnt = int(row[0] or 0)
    cost = Decimal(str(row[1] or 0)).quantize(Decimal("0.000001"))
    toks = int(row[2] or 0)
    return cnt, cost, toks
