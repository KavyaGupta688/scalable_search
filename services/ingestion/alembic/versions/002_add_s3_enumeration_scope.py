"""add S3 enumeration scope controls

Revision ID: 002
Revises: 001
Create Date: 2026-08-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("connectors", sa.Column("s3_prefix", sa.Text(), nullable=True))
    op.add_column(
        "connectors", sa.Column("enumeration_max_objects", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "connectors", sa.Column("enumeration_page_size", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("connectors", "enumeration_page_size")
    op.drop_column("connectors", "enumeration_max_objects")
    op.drop_column("connectors", "s3_prefix")
