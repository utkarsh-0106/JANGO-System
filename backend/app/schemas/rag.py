from pydantic import BaseModel
from typing import List, Optional, Literal


class RagRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5
    response_language: Literal["auto", "english", "hindi", "hinglish"] = "auto"


class RagResponse(BaseModel):
    answer: str
    sources: List[dict]
    usage: Optional[dict] = None
