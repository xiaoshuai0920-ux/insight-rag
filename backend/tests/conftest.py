"""Shared pytest fixtures. Uses the real PostgreSQL instance from docker-compose
(database insightrag_test) so pgvector paths are covered."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://insightrag:insightrag@localhost:5433/insightrag_test",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.core.security import hash_password  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    """Create schema in the test database once for the whole run.

    Uses DROP SCHEMA ... CASCADE instead of Base.metadata.drop_all because the
    documents <-> document_versions tables share a circular foreign-key pair
    (documents.current_version_id -> document_versions.id, and
    document_versions.document_id -> documents.id), which trips SQLAlchemy's
    circular-dependency detection during drop_all.
    """
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        Base.metadata.create_all(bind=conn)
    yield
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
        )


@pytest.fixture(scope="session")
def client():
    # Point the app's engine at the test DB
    import app.db.session as session_mod

    session_mod.engine = engine
    session_mod.SessionLocal = SessionLocal
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def user_token(client) -> str:
    resp = client.post(
        "/api/auth/register",
        json={"username": "testuser", "email": "test@example.com", "password": "Passw0rd123"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


@pytest.fixture(scope="session")
def auth_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="session")
def second_user_token(client) -> str:
    resp = client.post(
        "/api/auth/register",
        json={"username": "otheruser", "email": "other@example.com", "password": "Passw0rd123"},
    )
    return resp.json()["token"]
