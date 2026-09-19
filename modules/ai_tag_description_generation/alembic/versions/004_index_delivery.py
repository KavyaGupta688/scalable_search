"""Durable indexing handoff."""

from alembic import op
from modules.shared.delivery import DeliveryBase

revision = "004"
down_revision = "003_ingestion_zero_copy"
branch_labels = depends_on = None


def upgrade():
    DeliveryBase.metadata.create_all(op.get_bind())


def downgrade():
    op.drop_table("integration_outbox")
