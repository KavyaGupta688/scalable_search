"""Exercise 004 -> 014 with foreign records, then adopt module schemas twice."""

import os, subprocess, sys, uuid
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

root = Path("/app")
name = "legacy_acceptance_" + uuid.uuid4().hex[:8]
source = make_url(os.environ["DATABASE_URL_SYNC"])
with create_engine(source, isolation_level="AUTOCOMMIT").connect() as c:
    c.execute(text("CREATE DATABASE " + name))
url = source.set(database=name)
async_url = make_url(os.environ["DATABASE_URL"]).set(database=name)
env = dict(
    os.environ,
    DATABASE_URL_SYNC=url.render_as_string(hide_password=False),
    DATABASE_URL=async_url.render_as_string(hide_password=False),
    DATABASE_SCHEMA="public",
)


def alembic(revision):
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=root / "services/ingestion",
        env=env,
        check=True,
    )


alembic("004")
engine = create_engine(url)
# Use actual legacy Download models, plus preserved unrelated identity tables.
sys.path.insert(0, str(root / "services/download"))
from database.models import Base as DownloadBase, ForensicAuditLog, AsyncDownloadJob
from sqlalchemy.orm import Session

DownloadBase.metadata.create_all(engine)
with Session(engine) as session:
    session.add(
        ForensicAuditLog(
            download_id="legacy",
            user_id="legacy-user",
            user_email="legacy@example.com",
            s3_key="legacy-object",
            timestamp=1,
            iso_timestamp="1970-01-01T00:00:01Z",
            client_ip="127.0.0.1",
            token_str="synthetic-preserved-token",
            token_signature="synthetic",
            status="DELIVERED",
        )
    )
    session.add(
        AsyncDownloadJob(
            job_id="legacy",
            user_id="legacy-user",
            user_email="legacy@example.com",
            s3_keys_json='["legacy-object"]',
            status="COMPLETED",
            progress_pct=100,
        )
    )
    session.commit()
with engine.begin() as c:
    for table in ("users", "refresh_sessions"):
        c.execute(
            text(f"CREATE TABLE {table} (id text PRIMARY KEY, preserved text NOT NULL)")
        )
        c.execute(text(f"INSERT INTO {table} VALUES ('legacy','must survive')"))
    c.execute(
        text(
            "CREATE TABLE audit_events(event_id varchar(80) PRIMARY KEY,action varchar(80) NOT NULL,actor varchar(200) NOT NULL,entity_type varchar(120) NOT NULL,entity_id varchar(200) NOT NULL,occurred_at varchar(40) NOT NULL,metadata_json text NOT NULL)"
        )
    )
    c.execute(
        text(
            "INSERT INTO audit_events VALUES ('legacy','LEGACY','legacy-user','file','legacy','2026-01-01T00:00:00+00:00','{}')"
        )
    )
alembic("012")
with engine.connect() as c:
    assert (
        c.execute(
            text("SELECT token_str FROM forensic_audit_logs WHERE download_id='legacy'")
        ).scalar_one()
        == "synthetic-preserved-token"
    )
    assert (
        c.execute(
            text("SELECT progress_pct FROM async_download_jobs WHERE job_id='legacy'")
        ).scalar_one()
        == 100
    )
    for table in ("users", "refresh_sessions"):
        assert (
            c.execute(
                text(f"SELECT preserved FROM {table} WHERE id='legacy'")
            ).scalar_one()
            == "must survive"
        )
# Migration ownership moves these tables without interpreting or deleting legacy records.
for _ in range(2):
    subprocess.run(
        [sys.executable, "scripts/migrate_integration.py"],
        cwd=root,
        env=env,
        check=True,
    )
with engine.connect() as c:
    assert (
        c.execute(
            text(
                "SELECT token_str FROM download.forensic_audit_logs WHERE download_id='legacy'"
            )
        ).scalar_one()
        == "synthetic-preserved-token"
    )
    assert (
        c.execute(
            text(
                "SELECT progress_pct FROM download.async_download_jobs WHERE job_id='legacy'"
            )
        ).scalar_one()
        == 100
    )
    assert (
        c.execute(
            text("SELECT actor FROM audit.audit_events WHERE event_id='legacy'")
        ).scalar_one()
        == "legacy-user"
    )
    for table in ("public.users", "public.refresh_sessions"):
        assert (
            c.execute(
                text(f"SELECT preserved FROM {table} WHERE id='legacy'")
            ).scalar_one()
            == "must survive"
        )
    assert (
        c.execute(
            text("SELECT version_num FROM ingestion.alembic_version")
        ).scalar_one()
        == "014"
    )
    assert (
        c.execute(
            text("SELECT version_num FROM enrichment.ai_enrichment_alembic_version")
        ).scalar_one()
        == "004"
    )
print(
    "PASS: foreign authentication, forensic, and download records survived 004 -> 014 and repeated schema adoption; database "
    + name
)
