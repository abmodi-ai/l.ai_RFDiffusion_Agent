"""
Ligant.ai Database Connection Factory

Provides engine creation, session factory, and a context-managed database
session generator.  Supports local PostgreSQL (psycopg2) and Cloud SQL
(cloud-sql-python-connector + pg8000).
"""

from contextlib import contextmanager
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from frontend.app.config import get_settings


@lru_cache()
def get_engine() -> Engine:
    """
    Create and cache a SQLAlchemy Engine.

    * **cloud** environment with ``CLOUD_SQL_INSTANCE`` set:
      uses ``cloud-sql-python-connector`` with the ``pg8000`` driver.
    * **local** (default): uses ``psycopg2`` via the ``database_url`` property.
    """
    settings = get_settings()
    pool_kwargs = dict(
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )

    if settings.ENVIRONMENT == "cloud" and settings.CLOUD_SQL_INSTANCE:
        # Lazy import so that the cloud-sql dependency is only required in
        # production and not during local development.
        from google.cloud.sql.connector import Connector  # type: ignore[import-untyped]

        connector = Connector()

        def _get_cloud_conn():
            return connector.connect(
                settings.CLOUD_SQL_INSTANCE,
                "pg8000",
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                db=settings.DB_NAME,
            )

        engine = create_engine(
            "postgresql+pg8000://",
            creator=_get_cloud_conn,
            **pool_kwargs,
        )
    else:
        engine = create_engine(
            settings.database_url,
            **pool_kwargs,
        )

    return engine


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
