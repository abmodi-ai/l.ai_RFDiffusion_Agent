#!/usr/bin/env python3
"""
One-shot database initialisation script.

Creates all tables defined in the ORM models.  Safe to run multiple times —
``create_all`` is a no-op for tables that already exist.

Usage:
    python -m scripts.init_db          # from backend/
    python backend/scripts/init_db.py  # from project root
"""

import sys
from pathlib import Path

# Ensure the backend package is importable when running from project root.
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from app.config import get_settings
from app.db.connection import get_engine
from app.db.models import Base


def main() -> None:
    settings = get_settings()
    print(f"Database URL: postgresql://{settings.DB_USER}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")

    engine = get_engine()

    print("Creating tables …")
    Base.metadata.create_all(bind=engine)

    # List created tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables present ({len(tables)}):")
    for t in sorted(tables):
        print(f"  • {t}")

    print("\nDatabase initialisation complete.")


if __name__ == "__main__":
    main()
