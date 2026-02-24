"""
Ligant.ai Alembic Migration Environment

Configures Alembic to discover the SQLAlchemy metadata defined in
``frontend.app.db.models`` and run migrations in either offline or online
mode.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so that ``frontend.app.*`` imports
# resolve correctly regardless of how ``alembic`` is invoked.
# ---------------------------------------------------------------------------
_project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from frontend.app.db.models import Base  # noqa: E402

# ---------------------------------------------------------------------------
# Alembic Config object – provides access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging (unless we are running
# programmatically without an .ini file).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The target metadata for ``autogenerate`` support.
target_metadata = Base.metadata

# Allow the connection URL to be overridden by an environment variable,
# which is especially useful in CI and production environments.
_env_url = os.environ.get("SQLALCHEMY_URL")
if _env_url:
    config.set_main_option("sqlalchemy.url", _env_url)


# ---------------------------------------------------------------------------
# Offline migrations (generates SQL script without connecting to the DB)
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an ``Engine``,
    though an ``Engine`` is acceptable here as well.  By skipping the
    ``Engine`` creation we don't even need a DBAPI to be available.

    Calls to ``context.execute()`` here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (connects to the database)
# ---------------------------------------------------------------------------

def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we create an ``Engine`` and associate a connection
    with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
