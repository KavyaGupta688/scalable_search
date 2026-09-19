"""initial schema

Revision ID: 001
Revises: 
Create Date: 2026-08-26 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # ─── Connectors ─────────────────────────────────────────────────────────────
    op.create_table(
        'connectors',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('source_type', sa.Enum('S3', 'NAS_SMB', 'NAS_NFS', name='source_type_enum'), nullable=False),
        sa.Column('endpoint_url', sa.Text(), nullable=True),
        sa.Column('bucket', sa.Text(), nullable=True),
        sa.Column('addressing_style', sa.String(length=10), nullable=True),
        sa.Column('signature_version', sa.String(length=10), nullable=True),
        sa.Column('mount_path', sa.Text(), nullable=True),
        sa.Column('secret_path', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('verified', 'unverified', 'failed', name='connector_status_enum'), nullable=False, server_default='unverified'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("source_type IN ('S3', 'NAS_SMB', 'NAS_NFS')", name='ck_connectors_source_type'),
        sa.CheckConstraint("status IN ('verified', 'unverified', 'failed')", name='ck_connectors_status')
    )

    # ─── Documents ──────────────────────────────────────────────────────────────
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('checksum_sha256', sa.Text(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.Text(), nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('source_connector_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_ref', sa.Text(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tika_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['source_connector_id'], ['connectors.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('checksum_sha256', name='uq_documents_checksum')
    )
    op.create_index('idx_documents_checksum', 'documents', ['checksum_sha256'], unique=True)
    op.create_index('idx_documents_mime_type', 'documents', ['mime_type'], unique=False)
    op.create_index('idx_documents_source_connector', 'documents', ['source_connector_id'], unique=False)
    op.create_index('idx_documents_created_at', 'documents', ['created_at'], unique=False)

    # ─── Duplicate Links ────────────────────────────────────────────────────────
    op.create_table(
        'duplicate_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_connector_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_ref', sa.Text(), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['original_document_id'], ['documents.id'], ),
        sa.ForeignKeyConstraint(['source_connector_id'], ['connectors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_duplinks_original', 'duplicate_links', ['original_document_id'], unique=False)
    op.create_index('idx_duplinks_source_ref', 'duplicate_links', ['source_ref'], unique=False)

    # ─── Enumeration Checkpoints ────────────────────────────────────────────────
    op.create_table(
        'enumeration_checkpoints',
        sa.Column('connector_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('continuation_token', sa.Text(), nullable=True),
        sa.Column('last_scanned_path', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['connector_id'], ['connectors.id'], ),
        sa.PrimaryKeyConstraint('connector_id')
    )

def downgrade() -> None:
    op.drop_table('enumeration_checkpoints')
    op.drop_index('idx_duplinks_source_ref', table_name='duplicate_links')
    op.drop_index('idx_duplinks_original', table_name='duplicate_links')
    op.drop_table('duplicate_links')
    op.drop_index('idx_documents_created_at', table_name='documents')
    op.drop_index('idx_documents_source_connector', table_name='documents')
    op.drop_index('idx_documents_mime_type', table_name='documents')
    op.drop_index('idx_documents_checksum', table_name='documents')
    op.drop_table('documents')
    op.drop_table('connectors')

    # Drop enum types as well in PostgreSQL
    sa.Enum(name='source_type_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='connector_status_enum').drop(op.get_bind(), checkfirst=True)
