from pydantic import BaseModel
from typing import List, Optional


class RagRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5


class RagResponse(BaseModel):
    answer: str
    sources: List[dict]
    usage: Optional[dict] = None
