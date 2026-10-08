import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.security import verify_password
from backend.app.db import Base, get_db
from backend.app.main import app
from backend.app.models.user import User


TEST_DATABASE_URL = "sqlite:///./test_auth.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_dependency_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_function():
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_register_success():
    response = client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] == 1
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["is_active"] is True
    assert "hashed_password" not in data
    assert "password" not in data


def test_duplicate_email():
    payload = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePass123",
    }

    first = client.post("/api/auth/register", json=payload)
    second = client.post(
        "/api/auth/register",
        json={
            **payload,
            "username": "anotheruser",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "Email already registered"}


def test_duplicate_username():
    first = client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "first@example.com",
            "password": "SecurePass123",
        },
    )

    second = client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "second@example.com",
            "password": "SecurePass123",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "Username already registered"}


def test_password_is_hashed():
    password = "SecurePass123"

    response = client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": password,
        },
    )

    assert response.status_code == 201

    db = TestingSessionLocal()

    try:
        user = db.query(User).filter(
            User.email == "test@example.com"
        ).first()

        assert user is not None
        assert user.hashed_password != password
        assert verify_password(password, user.hashed_password)
    finally:
        db.close()


def test_successful_login():
    client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123",
        },
    )

    response = client.post(
        "/api/auth/login",
        data={
            "username": "test@example.com",
            "password": "SecurePass123",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_invalid_password():
    client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123",
        },
    )

    response = client.post(
        "/api/auth/login",
        data={
            "username": "test@example.com",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401


def test_me_without_token():
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_with_valid_token():
    client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123",
        },
    )

    login = client.post(
        "/api/auth/login",
        data={
            "username": "test@example.com",
            "password": "SecurePass123",
        },
    )

    token = login.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["is_active"] is True


def test_me_with_invalid_token():
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_inactive_user_cannot_access_me():
    db = TestingSessionLocal()

    user = User(
        username="inactive",
        email="inactive@example.com",
        hashed_password="not-a-real-password-hash",
        is_active=False,
        is_superuser=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    db.close()

    from backend.app.core.security import create_access_token

    token = create_access_token({"user_id": user.id})

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_short_password_rejected():
    response = client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Short1",
        },
    )

    assert response.status_code == 422
