from typing import Literal
from pydantic import BaseModel, Field


class UserSettingsUpdate(BaseModel):
    preferred_response_language: Literal["auto", "english", "hindi", "hinglish"] = "auto"
    retrieval_top_k: int = Field(default=5, ge=1, le=20)


class UserSettingsResponse(BaseModel):
    username: str
    email: str
    preferred_response_language: str
    retrieval_top_k: int
    theme: str = "gold-silver"
    ai_provider: str
    ai_model: str


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
