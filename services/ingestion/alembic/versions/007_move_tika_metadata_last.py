"""Move documents.tika_metadata to the final physical column position.

Revision ID: 007
Revises: 006
Create Date: 2026-09-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL has no ALTER COLUMN POSITION operation. Recreate the nullable
    # JSONB column and preserve every existing value. As the only newly added
    # documents column in this revision, it becomes the final physical column.
    op.alter_column(
        "documents", "tika_metadata", new_column_name="tika_metadata_previous"
    )
    op.add_column(
        "documents",
        sa.Column(
            "tika_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.execute("UPDATE documents SET tika_metadata = tika_metadata_previous")
    op.drop_column("documents", "tika_metadata_previous")


def downgrade() -> None:
    # Column order has no SQL semantics, so restoring the previous position
    # would require another full data rewrite with no functional benefit.
    pass
