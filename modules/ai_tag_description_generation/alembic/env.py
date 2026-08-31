"""
Alembic environment configuration.

Loads DATABASE_URL_SYNC from the .env file and configures Alembic to use
the app's SQLAlchemy Base metadata for autogenerate support.

NOTE: We avoid fully importing app.db because it eagerly creates an asyncpg
engine at module level. Instead, we intercept the import so that app.db only
exposes Base, while letting the rest of the app package load normally.
"""
import os
import sys
import types
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlalchemy.orm import declarative_base

# Ensure the module root (ai_tag_description_generation/) is on sys.path
# so that `from app.* import ...` works correctly.
MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MODULE_ROOT not in sys.path:
    sys.path.insert(0, MODULE_ROOT)

# Load .env from the module root (same directory as alembic.ini)
load_dotenv(os.path.join(MODULE_ROOT, ".env"))

# Alembic Config object — provides access to values in alembic.ini
config = context.config

# Set sqlalchemy.url from the environment variable
database_url = os.environ.get("DATABASE_URL_SYNC")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Build a lightweight stand-in for `app.db` that exposes only Base.
# This avoids importing the real app.db which eagerly creates an asyncpg
# engine (requiring the asyncpg package to be installed).
# ---------------------------------------------------------------------------
Base = declarative_base()

# Create the fake app.db module and register it BEFORE importing app.models
_fake_db = types.ModuleType("app.db")
_fake_db.Base = Base

# We also need a fake app.config so app.db doesn't try to import it
_fake_config = types.ModuleType("app.config")

# Import the real app package first so submodule resolution works
import app  # noqa: F401 — ensures `app` is a real package in sys.modules

# Now override just app.db and app.config with our fakes
sys.modules["app.db"] = _fake_db
sys.modules["app.config"] = _fake_config

# Import models — they register tables on our Base via `from app.db import Base`
import app.models  # noqa: F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    Useful for reviewing migration SQL or applying via a DBA workflow.
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


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Connects directly to the database and applies migrations.
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
