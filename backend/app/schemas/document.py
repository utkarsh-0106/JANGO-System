from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

class DocumentCreate(BaseModel):
    filename: str
    stored_filename: str
    file_size: int
    content_type: str
    status: str

class DocumentResponse(DocumentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    processing_error: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    ingestion_attempts: int = 0

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