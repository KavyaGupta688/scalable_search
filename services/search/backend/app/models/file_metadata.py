from sqlalchemy import (
    BigInteger,
    Column,
    String,
    Integer,
    DateTime,
    Text,
    Boolean,
    Float,
    JSON,
)
from datetime import datetime, timezone
from app.db.postgres import Base


class FileMetadata(Base):
    __tablename__ = "file_metadata"
    published = Column(Boolean, default=False, nullable=False)
    enrichment_status = Column(String(30), nullable=False, default="pending")
    vendor_metadata = Column(JSON, default=dict)
    ai_metadata_version = Column(String(200))

    # Ingestion Core
    file_id = Column(String(64), primary_key=True, index=True)
    dataset_id = Column(String(64), index=True, nullable=False)
    dataset_name = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False, index=True)
    file_type = Column(
        String(50), nullable=False, index=True
    )  # image, video, audio, document, csv
    mime_type = Column(String(100), nullable=False)
    file_size = Column(BigInteger, nullable=False)  # in bytes
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)  # in seconds for audio/video
    thumbnail_url = Column(String(512), nullable=True)
    preview_url = Column(String(512), nullable=True)
    ingested_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    source_batch = Column(String(100), nullable=True)
    checksum = Column(String(128), nullable=False)

    # AI Tag and Description Generation
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    tags = Column(JSON, default=list)  # list of strings
    category = Column(String(100), nullable=False, index=True)
    content_summary = Column(Text, nullable=True)
    ocr_text = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    pii_detected = Column(Boolean, default=False, index=True)
    nsfw_detected = Column(Boolean, default=False)
    ai_generated = Column(Boolean, default=False, index=True)
    embedding_model = Column(String(100), default="clip-ViT-B-32")
    embedding_version = Column(String(50), default="v1.0")
    embedding_status = Column(String(50), default="INDEXED")  # INDEXED, PENDING, FAILED

    # Analytics / Auditing
    download_count = Column(Integer, default=0)
    file_preview_count = Column(Integer, default=0)
    interaction_timestamp = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
