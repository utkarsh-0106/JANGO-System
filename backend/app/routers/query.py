from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict
from backend.app.schemas.rag import RagRequest, RagResponse
from backend.app.services.rag import RagService
from backend.app.db import get_db
from backend.app.models import Document as DocumentModel

router = APIRouter(prefix="/api/v1")

@router.post("/query", response_model=RagResponse)
async def query_rag(request: RagRequest, db: Session = Depends(get_db)):
    rag_service = RagService()
    result = rag_service.query(request.question, request.top_k)
    return result

@router.post("/reprocess/{document_id}", response_model=bool)
async def reprocess_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    rag_service = RagService()
    success = rag_service.reprocess_document(document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reprocess document"
        )
    return True

@router.delete("/delete/{document_id}", response_model=bool)
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    rag_service = RagService()
    rag_service.delete_document_vectors(document_id)
    return True