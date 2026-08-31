"""
Database connection manager and query layer.
Supports AWS RDS PostgreSQL, Amazon Aurora, local PostgreSQL (via psycopg2 & SQLAlchemy)
with automatic fallback to SQLite for local development.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from config import DATABASE_URL, SQLITE_DB_PATH
from database.models import Base, ForensicAuditLog, AsyncDownloadJob


class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self.db_type = "UNKNOWN"
        self._init_engine()

    def _init_engine(self):
        # 1. Try connecting to PostgreSQL / AWS RDS if DATABASE_URL starts with postgresql
        if DATABASE_URL.startswith("postgresql"):
            try:
                self.engine = create_engine(
                    DATABASE_URL,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=300,
                    connect_args={"connect_timeout": 10}
                )
                # Test connection
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))

                if "rds.amazonaws.com" in DATABASE_URL:
                    self.db_type = "AWS RDS PostgreSQL"
                else:
                    self.db_type = "PostgreSQL"

                print(f"[DB] Successfully connected to {self.db_type}: {DATABASE_URL.split('@')[-1]}")
            except Exception as e:
                print(f"[DB WARNING] PostgreSQL/RDS connection failed: {e}. Falling back to SQLite local database.")
                self.engine = create_engine(
                    f"sqlite:///{SQLITE_DB_PATH}",
                    connect_args={"check_same_thread": False}
                )
                self.db_type = "SQLite (Fallback)"
        else:
            self.engine = create_engine(
                f"sqlite:///{SQLITE_DB_PATH}",
                connect_args={"check_same_thread": False}
            )
            self.db_type = "SQLite"

        # Create all tables if they don't exist
        Base.metadata.create_all(self.engine)
        self.session_factory = scoped_session(sessionmaker(bind=self.engine))

    def get_session(self):
        return self.session_factory()

    def get_health_status(self) -> Dict[str, Any]:
        """Checks live database connectivity and stats."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {
                "connected": True,
                "engine": self.db_type,
                "connection_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else str(SQLITE_DB_PATH)
            }
        except Exception as e:
            return {
                "connected": False,
                "engine": self.db_type,
                "error": str(e)
            }

    # --- Audit Log Queries ---

    def record_download(
        self,
        download_id: str,
        user_id: str,
        user_email: str,
        s3_key: str,
        timestamp: int,
        client_ip: str,
        token_str: str,
        file_size_bytes: int = 0,
        status: str = "DELIVERED",
        notes: str = ""
    ) -> bool:
        """Inserts or updates a forensic audit trail entry."""
        iso_ts = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).isoformat()
        sig = token_str.split(".")[-1] if "." in token_str else ""

        session = self.get_session()
        try:
            record = session.query(ForensicAuditLog).filter_by(download_id=download_id).first()
            if not record:
                record = ForensicAuditLog(
                    download_id=download_id,
                    user_id=user_id,
                    user_email=user_email,
                    s3_key=s3_key,
                    timestamp=timestamp,
                    iso_timestamp=iso_ts,
                    client_ip=client_ip,
                    token_str=token_str,
                    token_signature=sig,
                    file_size_bytes=file_size_bytes,
                    status=status,
                    notes=notes
                )
                session.add(record)
            else:
                record.status = status
                record.file_size_bytes = file_size_bytes
                record.notes = notes
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"[DB Error] Failed to record download: {e}")
            return False
        finally:
            session.close()

    def find_by_download_id(self, download_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            record = session.query(ForensicAuditLog).filter_by(download_id=download_id).first()
            return record.to_dict() if record else None
        finally:
            session.close()

    def find_by_signature(self, signature: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            record = session.query(ForensicAuditLog).filter_by(token_signature=signature).first()
            return record.to_dict() if record else None
        finally:
            session.close()

    def list_all_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            records = session.query(ForensicAuditLog).order_by(ForensicAuditLog.timestamp.desc()).limit(limit).all()
            return [r.to_dict() for r in records]
        finally:
            session.close()

    # --- Celery Async Download Job Queries ---

    def create_async_job(
        self,
        job_id: str,
        user_id: str,
        user_email: str,
        s3_keys: List[str]
    ) -> bool:
        session = self.get_session()
        try:
            job = session.query(AsyncDownloadJob).filter_by(job_id=job_id).first()
            if not job:
                job = AsyncDownloadJob(
                    job_id=job_id,
                    user_id=user_id,
                    user_email=user_email,
                    s3_keys_json=json.dumps(s3_keys),
                    total_files=len(s3_keys),
                    status="PENDING",
                    progress_pct=0
                )
                session.add(job)
            else:
                job.user_id = user_id
                job.user_email = user_email
                job.s3_keys_json = json.dumps(s3_keys)
                job.total_files = len(s3_keys)
                job.status = "PENDING"
                job.progress_pct = 0
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"[DB Error] Failed to create async job: {e}")
            return False
        finally:
            session.close()

    def update_job_progress(
        self,
        job_id: str,
        status: str,
        progress_pct: int,
        output_filename: Optional[str] = None,
        file_size_bytes: int = 0,
        error_message: Optional[str] = None
    ) -> bool:
        session = self.get_session()
        try:
            job = session.query(AsyncDownloadJob).filter_by(job_id=job_id).first()
            if job:
                job.status = status
                job.progress_pct = progress_pct
                if output_filename:
                    job.output_filename = output_filename
                if file_size_bytes > 0:
                    job.file_size_bytes = file_size_bytes
                if error_message:
                    job.error_message = error_message
                if status in ("COMPLETED", "FAILED"):
                    job.completed_at = datetime.datetime.utcnow()
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"[DB Error] Failed to update job: {e}")
            return False
        finally:
            session.close()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            job = session.query(AsyncDownloadJob).filter_by(job_id=job_id).first()
            return job.to_dict() if job else None
        finally:
            session.close()


# Singleton database instance
db = DatabaseManager()
