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
    op.create_table(
        'connectors',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'documents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('connector_id', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('content_hash', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['connector_id'], ['connectors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'duplicate_links',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('duplicate_of_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.ForeignKeyConstraint(['duplicate_of_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'enumeration_checkpoints',
        sa.Column('connector_id', sa.String(), nullable=False),
        sa.Column('checkpoint_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['connector_id'], ['connectors.id'], ),
        sa.PrimaryKeyConstraint('connector_id')
    )

def downgrade() -> None:
    op.drop_table('enumeration_checkpoints')
    op.drop_table('duplicate_links')
    op.drop_table('documents')
    op.drop_table('connectors')
