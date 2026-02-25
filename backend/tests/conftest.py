"""
Shared pytest fixtures for the Ligant.ai backend test suite.

Uses an in-memory SQLite database with type adapters for PostgreSQL-specific
column types (JSONB → JSON, UUID → CHAR(36)).
"""

import sqlite3
import uuid

import pytest
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, User

# Register UUID adapter for SQLite — converts uuid.UUID to str on bind
sqlite3.register_adapter(uuid.UUID, str)


def _create_sqlite_engine():
    """Create an in-memory SQLite engine with PG type compatibility."""
    # Patch column types on the metadata (in-place) for SQLite DDL compat
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
            elif isinstance(column.type, PG_UUID):
                column.type = String(36)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session():
    """In-memory SQLite session for unit tests."""
    engine = _create_sqlite_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def test_user(db_session):
    """Create and return a test user in the in-memory DB."""
    from app.auth_utils import hash_password

    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        email_lower="test@example.com",
        password_hash=hash_password("TestPass123!"),
        display_name="Test User",
    )
    db_session.add(user)
    db_session.flush()
    return user


class FakeSettings:
    """Minimal settings object for JWT tests."""

    JWT_SECRET_KEY = "test-secret-key-for-tests-only"
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_DAYS = 7
    BACKEND_API_KEY = "test-api-key"
    ANTHROPIC_API_KEY = "sk-test"


@pytest.fixture()
def settings():
    return FakeSettings()
