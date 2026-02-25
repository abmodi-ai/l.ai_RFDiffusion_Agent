"""
Ligant.ai Database Connection Factory (Backend)

Provides engine creation, session factory, and both a context-managed
``get_db()`` for use in the agent code and a FastAPI-compatible
``get_db_session()`` dependency.
"""

from contextlib import contextmanager
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache()
def get_engine() -> Engine:
    """
    Create and cache a SQLAlchemy Engine.

    Uses psycopg2 via the ``database_url`` property on Settings.
    """
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_timeout=10,
    )


@lru_cache()
def get_session_factory() -> sessionmaker[Session]:
    """Return a cached ``sessionmaker`` bound to the application engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager that yields a SQLAlchemy ``Session``.

    Automatically commits on clean exit or rolls back on exception.

    Usage::

        with get_db() as db:
            db.add(some_model)
    """
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy ``Session``.

    Usage in a route::

        @router.get("/foo")
        def foo(db: Session = Depends(get_db_session)):
            ...
    """
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
