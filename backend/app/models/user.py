from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from backend.app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Telegram account linking. Tokens are stored as SHA-256 hashes, never plaintext.
    telegram_user_id = Column(BigInteger, nullable=True, unique=True, index=True)
    telegram_link_token_hash = Column(String(64), nullable=True, index=True)
    telegram_link_expires_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return (
            f"User(id={self.id}, "
            f"username={self.username}, "
            f"email={self.email})"
        )
