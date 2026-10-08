from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.api.auth import get_current_user
from backend.app.db import Base, get_db
from backend.app.main import app


DATABASE_URL = "sqlite:///./backend/tests/test_documents.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class MockUser:
    id = 1
    username = "document_test_user"
    email = "document@example.com"
    is_active = True


def create_test_pdf():
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(100, 750, "Test PDF document")
    pdf.save()
    buffer.seek(0)
    return buffer.read()


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        return MockUser()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        Base.metadata.drop_all(bind=engine)

def test_upload_document(client):
    pdf_content = create_test_pdf()

    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "test.pdf",
                pdf_content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["filename"] == "test.pdf"
    assert data["content_type"] == "application/pdf"
    assert data["file_size"] == len(pdf_content)
