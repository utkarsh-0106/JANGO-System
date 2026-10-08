from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class DocumentCreate(BaseModel):
    filename: str
    stored_filename: str
    file_size: int
    content_type: str
    status: str

class DocumentResponse(DocumentCreate):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

class DocumentStatusResponse(BaseModel):
    status: str
    file_exists: bool

class RAGQuery(BaseModel):
    query: str
    source_ids: Optional[List[int]] = None
class RAGResponse(BaseModel):
    answer: str
    sources: List[str]
    timestamp: datetime