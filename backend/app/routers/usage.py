from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.auth import get_current_user
from backend.app.db import get_db
from backend.app.models.user import User
from backend.app.schemas.ai_usage import RecentUsageItem, UsageSummary
from backend.app.services.ai_usage import get_recent_usage, get_usage_summary

router = APIRouter(prefix="/usage", tags=["ai-usage"])


@router.get("/summary", response_model=UsageSummary)
def usage_summary(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_usage_summary(db, current_user.id, days=days)


@router.get("/recent", response_model=list[RecentUsageItem])
def recent_usage(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [
        {
            "id": event.id,
            "provider": event.provider,
            "model": event.model,
            "operation": event.operation,
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "total_tokens": event.total_tokens,
            "tokens_estimated": event.tokens_estimated,
            "latency_ms": event.latency_ms,
            "estimated_cost_usd": event.estimated_cost_usd,
            "status": event.status,
            "created_at": event.created_at.isoformat(),
        }
        for event in get_recent_usage(db, current_user.id, limit=limit)
    ]
