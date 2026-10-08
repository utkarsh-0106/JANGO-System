from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from backend.app.db import Base


class AIUsage(Base):
    """Per-request AI observability record, scoped to the authenticated user."""

    __tablename__ = "ai_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    provider = Column(String(50), nullable=False)
    model = Column(String(150), nullable=False)
    operation = Column(String(50), nullable=False, default="rag_query")

    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    tokens_estimated = Column(Boolean, nullable=False, default=False)

    latency_ms = Column(Float, nullable=False, default=0)
    estimated_cost_usd = Column(Float, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="success")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
