"""Configurable model pricing (USD per 1M tokens)."""

from decimal import Decimal
from typing import Optional

from app.config import get_settings, parse_pricing_json


def estimate_cost_usd(model: Optional[str], prompt_tokens: int, completion_tokens: int) -> Decimal:
    table = parse_pricing_json(get_settings().pricing_json)
    if not model:
        model = ""
    rates = table.get(model) or table.get(model.split("/")[-1] if "/" in model else model)
    if not rates:
        rates = table.get("gpt-5") or table.get("gpt-4o") or {"prompt_per_million": 1.25, "completion_per_million": 10.0}

    p = Decimal(str(rates["prompt_per_million"]))
    c = Decimal(str(rates["completion_per_million"]))
    prompt_cost = (Decimal(prompt_tokens) / Decimal(1_000_000)) * p
    completion_cost = (Decimal(completion_tokens) / Decimal(1_000_000)) * c
    return (prompt_cost + completion_cost).quantize(Decimal("0.000001"))
