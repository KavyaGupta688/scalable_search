"""Explicit, additive download upgrades. Never modify other module schemas."""
from sqlalchemy import text


def upgrade(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS integration_migrations (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"))
        conn.execute(text("SELECT pg_advisory_xact_lock(782302)"))
        if conn.scalar(text("SELECT 1 FROM integration_migrations WHERE version=2")):
            return
        for definition in (
            "display_name VARCHAR(255)", "client_ip VARCHAR(64)",
            "execution_mode VARCHAR(20)", "delivery_started_at TIMESTAMPTZ",
        ):
            conn.execute(text("ALTER TABLE document_download_jobs ADD COLUMN IF NOT EXISTS " + definition))
        conn.execute(text("INSERT INTO integration_migrations(version) VALUES (2)"))


if __name__ == "__main__":
    from modules.shared.integration import database_engine
    upgrade(database_engine("download"))
    print("Download migration 2 applied; existing records preserved")
