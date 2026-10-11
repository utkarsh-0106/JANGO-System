import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.auth import get_current_user
from backend.app.db import get_db
from backend.app.schemas.rag import RagRequest, RagResponse
from backend.app.services.rag import query_rag


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/rag",
    tags=["rag"],
)


@router.post("/query", response_model=RagResponse)
def rag_query(
    rag_request: RagRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return query_rag(
            rag_request,
            current_user.id,
            db=db,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("Unhandled RAG route failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the question.",
        ) from exc
