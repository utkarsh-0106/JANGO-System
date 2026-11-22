from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db import Base
from backend.app.models import Document, User
from backend.app.services import documents
from backend.app.services import lexical_search, vector_store


def make_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    db = TestingSession()

    user = User(
        username="delete_test_user",
        email="delete@example.com",
        hashed_password="test-hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return engine, db, user


def make_document(db, user, file_path):
    document = Document(
        user_id=user.id,
        filename="sample.pdf",
        stored_filename="sample-stored.pdf",
        file_path=str(file_path),
        file_size=100,
        content_type="application/pdf",
        status="ready",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_delete_document_cleans_both_indexes_and_file(tmp_path, monkeypatch):
    engine, db, user = make_database()
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"sample PDF content")
    document = make_document(db, user, file_path)

    vector_calls = []
    lexical_calls = []

    monkeypatch.setattr(
        vector_store,
        "delete_document_vectors",
        lambda document_id: vector_calls.append(document_id),
    )
    monkeypatch.setattr(
        lexical_search,
        "delete_document_chunks",
        lambda document_id, user_id: lexical_calls.append(
            (document_id, user_id)
        ),
    )

    try:
        result = documents.delete_document(db, document.id, user.id)

        assert result is True
        assert vector_calls == [document.id]
        assert lexical_calls == [(document.id, user.id)]
        assert not file_path.exists()
        assert db.query(Document).filter(Document.id == document.id).first() is None
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_delete_document_preserves_file_and_record_if_lexical_cleanup_fails(
    tmp_path, monkeypatch
):
    engine, db, user = make_database()
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"sample PDF content")
    document = make_document(db, user, file_path)

    vector_calls = []

    monkeypatch.setattr(
        vector_store,
        "delete_document_vectors",
        lambda document_id: vector_calls.append(document_id),
    )

    def fail_lexical_cleanup(document_id, user_id):
        raise RuntimeError("Lexical index unavailable")

    monkeypatch.setattr(
        lexical_search,
        "delete_document_chunks",
        fail_lexical_cleanup,
    )

    try:
        try:
            documents.delete_document(db, document.id, user.id)
            assert False, "Expected lexical cleanup failure"
        except RuntimeError as exc:
            assert "Lexical index unavailable" in str(exc)

        retained = (
            db.query(Document)
            .filter(
                Document.id == document.id,
                Document.user_id == user.id,
            )
            .first()
        )

        assert vector_calls == [document.id]
        assert file_path.exists()
        assert retained is not None
        assert retained.status == "failed"
        assert "Deletion did not complete" in retained.processing_error
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_delete_document_attempts_lexical_cleanup_if_vector_cleanup_fails(
    tmp_path, monkeypatch
):
    engine, db, user = make_database()
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"sample PDF content")
    document = make_document(db, user, file_path)

    lexical_calls = []

    def fail_vector_cleanup(document_id):
        raise RuntimeError("Chroma unavailable")

    monkeypatch.setattr(
        vector_store,
        "delete_document_vectors",
        fail_vector_cleanup,
    )
    monkeypatch.setattr(
        lexical_search,
        "delete_document_chunks",
        lambda document_id, user_id: lexical_calls.append(
            (document_id, user_id)
        ),
    )

    try:
        try:
            documents.delete_document(db, document.id, user.id)
            assert False, "Expected vector cleanup failure"
        except RuntimeError as exc:
            assert "Chroma unavailable" in str(exc)

        retained = (
            db.query(Document)
            .filter(Document.id == document.id)
            .first()
        )

        assert lexical_calls == [(document.id, user.id)]
        assert file_path.exists()
        assert retained is not None
        assert retained.status == "failed"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
