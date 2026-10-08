from pydantic import BaseModel, ConfigDict
from typing import List


class UsageModelSummary(BaseModel):
    provider: str
    model: str
    requests: int
    tokens: int
    cost_usd: float


class UsageDailyPoint(BaseModel):
    date: str
    requests: int
    tokens: int
    cost_usd: float


class UsagePricing(BaseModel):
    input_per_1m_usd: float
    output_per_1m_usd: float
    note: str


class UsageSummary(BaseModel):
    period_days: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    average_latency_ms: float
    models: List[UsageModelSummary]
    daily: List[UsageDailyPoint]
    pricing: UsagePricing


class RecentUsageItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    model: str
    operation: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    tokens_estimated: bool
    latency_ms: float
    estimated_cost_usd: float
    status: str
    created_at: str
