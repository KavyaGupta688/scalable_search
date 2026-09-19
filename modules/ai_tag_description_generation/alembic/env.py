"""
Alembic environment configuration.

Loads DATABASE_URL_SYNC from the .env file and configures Alembic to use
the AI module's SQLAlchemy metadata. The ingestion source table is external
and is referenced only by revision 002's database-level foreign key.
"""

import os
from logging.config import fileConfig

from alembic import context
from modules.shared.integration import connection_args, schema_name
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Resolve the module-local .env. Alembic is run from the repository root in
# Docker, where the `modules.*` package is directly importable.
MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load .env from the module root (same directory as alembic.ini)
load_dotenv(os.path.join(MODULE_ROOT, ".env"))

# Alembic Config object — provides access to values in alembic.ini
config = context.config

# Set sqlalchemy.url from the environment variable
database_url = os.environ.get("DATABASE_URL_SYNC")
if database_url:
    # ConfigParser treats percent signs in URL-encoded passwords as
    # interpolation markers unless they are escaped.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from modules.ai_tag_description_generation.app.db import Base
from modules.ai_tag_description_generation.app import models  # noqa: F401

target_metadata = Base.metadata
VERSION_TABLE = "ai_enrichment_alembic_version"


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
        version_table=VERSION_TABLE,
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
        connect_args=connection_args(database_url, schema_name("enrichment")),
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=VERSION_TABLE,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
