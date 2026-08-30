"""
SQLAlchemy ORM Models for PostgreSQL / SQLite Forensic Database.
"""
import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, BigInteger
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ForensicAuditLog(Base):
    """
    Immutable audit log table linking every cryptographic watermark to the user session.
    """
    __tablename__ = "forensic_audit_logs"

    download_id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, index=True)
    user_email = Column(String(255), nullable=False)
    s3_key = Column(Text, nullable=False, index=True)
    timestamp = Column(BigInteger, nullable=False, index=True)
    iso_timestamp = Column(String(64), nullable=False)
    client_ip = Column(String(64), nullable=False)
    token_str = Column(Text, nullable=False)
    token_signature = Column(String(128), nullable=False, index=True)
    file_size_bytes = Column(BigInteger, default=0)
    status = Column(String(64), default="DELIVERED")
    notes = Column(Text, default="")

    def to_dict(self):
        return {
            "download_id": self.download_id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "s3_key": self.s3_key,
            "timestamp": self.timestamp,
            "iso_timestamp": self.iso_timestamp,
            "client_ip": self.client_ip,
            "token_str": self.token_str,
            "token_signature": self.token_signature,
            "file_size_bytes": self.file_size_bytes,
            "status": self.status,
            "notes": self.notes
        }


class AsyncDownloadJob(Base):
    """
    Table tracking Celery + Redis background download and watermarking tasks.
    """
    __tablename__ = "async_download_jobs"

    job_id = Column(String(64), primary_key=True, index=True)
    celery_task_id = Column(String(64), nullable=True, index=True)
    user_id = Column(String(128), nullable=False, index=True)
    user_email = Column(String(255), nullable=False)
    s3_keys_json = Column(Text, nullable=False)
    total_files = Column(Integer, default=1)
    status = Column(String(32), default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    progress_pct = Column(Integer, default=0)
    output_filename = Column(String(255), nullable=True)
    file_size_bytes = Column(BigInteger, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "celery_task_id": self.celery_task_id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "s3_keys": self.s3_keys_json,
            "total_files": self.total_files,
            "status": self.status,
            "progress_pct": self.progress_pct,
            "output_filename": self.output_filename,
            "file_size_bytes": self.file_size_bytes,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
