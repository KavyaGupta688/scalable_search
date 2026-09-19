"""Preserve archived source credentials and history."""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = depends_on = None


def upgrade():
    op.add_column("connectors", sa.Column("archived_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("connectors", "archived_at")
