from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.auth import get_current_user
from backend.app.core.security import hash_password, verify_password
from backend.app.db import get_db
from backend.app.models.user import User
from backend.app.schemas.settings import PasswordChangeRequest, UserSettingsResponse, UserSettingsUpdate
from backend.app.services.ai_config import normalize_provider
from backend.app.settings import settings as app_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _current_ai_model() -> tuple[str, str]:
    provider = normalize_provider(app_settings.LLM_PROVIDER)
    models = {
        "gemini": app_settings.GEMINI_CHAT_MODEL,
        "groq": app_settings.GROQ_CHAT_MODEL,
        "claude": app_settings.ANTHROPIC_CHAT_MODEL,
        "ollama": app_settings.OLLAMA_CHAT_MODEL,
    }
    return provider, models.get(provider, "Configured by environment")


@router.get("", response_model=UserSettingsResponse)
def get_settings(current_user: User = Depends(get_current_user)):
    provider, model = _current_ai_model()
    return UserSettingsResponse(
        username=current_user.username,
        email=current_user.email,
        preferred_response_language=current_user.preferred_response_language or "auto",
        retrieval_top_k=current_user.retrieval_top_k or 5,
        ai_provider=provider,
        ai_model=model,
    )


@router.put("")
def update_settings(
    payload: UserSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.preferred_response_language = payload.preferred_response_language
    current_user.retrieval_top_k = payload.retrieval_top_k
    db.commit()
    db.refresh(current_user)
    return {
        "message": "Preferences saved successfully.",
        "preferred_response_language": current_user.preferred_response_language,
        "retrieval_top_k": current_user.retrieval_top_k,
    }


@router.put("/password")
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    if verify_password(payload.new_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must differ from the current password.")
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully."}
