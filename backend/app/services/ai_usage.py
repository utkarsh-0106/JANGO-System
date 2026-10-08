from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.ai_usage import AIUsage
from backend.app.settings import settings


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_token_usage(response: Any, prompt_text: str = "", output_text: str = "") -> dict[str, int | bool]:
    """Extract provider-reported usage with a conservative local fallback.

    LangChain providers expose usage in slightly different locations. We prefer
    provider-reported counts and only fall back to a rough character-based
    estimate when the provider does not expose usage metadata.
    """
    candidates: list[Mapping[str, Any]] = []

    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, Mapping):
        candidates.append(usage)

    metadata = getattr(response, "response_metadata", None)
    if isinstance(metadata, Mapping):
        for key in ("usage_metadata", "token_usage", "usage"):
            nested = metadata.get(key)
            if isinstance(nested, Mapping):
                candidates.append(nested)
        candidates.append(metadata)

    input_tokens = output_tokens = total_tokens = None

    for data in candidates:
        input_tokens = input_tokens or _as_int(
            data.get("input_tokens")
            or data.get("prompt_tokens")
            or data.get("prompt_token_count")
        )
        output_tokens = output_tokens or _as_int(
            data.get("output_tokens")
            or data.get("completion_tokens")
            or data.get("candidates_token_count")
        )
        total_tokens = total_tokens or _as_int(
            data.get("total_tokens")
            or data.get("total_token_count")
        )

    estimated = False

    if input_tokens is None:
        input_tokens = max(1, round(len(prompt_text) / 4)) if prompt_text else 0
        estimated = True

    if output_tokens is None:
        output_tokens = max(1, round(len(output_text) / 4)) if output_text else 0
        estimated = True

    if total_tokens is None:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated": estimated,
    }


def calculate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost from configurable USD / 1M token rates."""
    input_cost = (input_tokens / 1_000_000) * settings.AI_INPUT_COST_PER_1M_USD
    output_cost = (output_tokens / 1_000_000) * settings.AI_OUTPUT_COST_PER_1M_USD
    return round(input_cost + output_cost, 8)


def record_usage(
    db: Session,
    *,
    user_id: int,
    provider: str,
    model: str,
    operation: str,
    usage: dict[str, int | bool],
    latency_ms: float,
    status: str = "success",
) -> AIUsage:
    input_tokens = int(usage.get("input_tokens", 0))
    output_tokens = int(usage.get("output_tokens", 0))
    total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens))

    event = AIUsage(
        user_id=user_id,
        provider=provider,
        model=model,
        operation=operation,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        tokens_estimated=bool(usage.get("estimated", False)),
        latency_ms=round(float(latency_ms), 2),
        estimated_cost_usd=calculate_cost_usd(input_tokens, output_tokens),
        status=status,
    )

    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_usage_summary(db: Session, user_id: int, days: int = 30) -> dict:
    days = max(1, min(days, 365))
    cutoff = datetime.utcnow() - timedelta(days=days - 1)

    events = (
        db.query(AIUsage)
        .filter(AIUsage.user_id == user_id, AIUsage.created_at >= cutoff)
        .order_by(AIUsage.created_at.asc())
        .all()
    )

    successful = [event for event in events if event.status == "success"]
    total_requests = len(events)
    total_tokens = sum(event.total_tokens for event in events)
    input_tokens = sum(event.input_tokens for event in events)
    output_tokens = sum(event.output_tokens for event in events)
    estimated_cost = round(sum(event.estimated_cost_usd for event in events), 8)
    avg_latency = (
        round(sum(event.latency_ms for event in successful) / len(successful), 2)
        if successful
        else 0
    )

    by_model: dict[str, dict] = {}
    for event in events:
        key = f"{event.provider}/{event.model}"
        item = by_model.setdefault(
            key,
            {
                "provider": event.provider,
                "model": event.model,
                "requests": 0,
                "tokens": 0,
                "cost_usd": 0,
            },
        )
        item["requests"] += 1
        item["tokens"] += event.total_tokens
        item["cost_usd"] = round(item["cost_usd"] + event.estimated_cost_usd, 8)

    daily: dict[str, dict] = {}
    for offset in range(days):
        day = (cutoff + timedelta(days=offset)).date().isoformat()
        daily[day] = {"date": day, "requests": 0, "tokens": 0, "cost_usd": 0}

    for event in events:
        day = event.created_at.date().isoformat()
        if day not in daily:
            daily[day] = {"date": day, "requests": 0, "tokens": 0, "cost_usd": 0}
        daily[day]["requests"] += 1
        daily[day]["tokens"] += event.total_tokens
        daily[day]["cost_usd"] = round(
            daily[day]["cost_usd"] + event.estimated_cost_usd, 8
        )

    return {
        "period_days": days,
        "total_requests": total_requests,
        "successful_requests": len(successful),
        "failed_requests": total_requests - len(successful),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost,
        "average_latency_ms": avg_latency,
        "models": sorted(by_model.values(), key=lambda item: item["tokens"], reverse=True),
        "daily": list(daily.values()),
        "pricing": {
            "input_per_1m_usd": settings.AI_INPUT_COST_PER_1M_USD,
            "output_per_1m_usd": settings.AI_OUTPUT_COST_PER_1M_USD,
            "note": "Local Ollama usage is treated as $0.00. Configure rates for cloud providers.",
        },
    }


def get_recent_usage(db: Session, user_id: int, limit: int = 10) -> list[AIUsage]:
    limit = max(1, min(limit, 50))
    return (
        db.query(AIUsage)
        .filter(AIUsage.user_id == user_id)
        .order_by(AIUsage.created_at.desc())
        .limit(limit)
        .all()
    )
