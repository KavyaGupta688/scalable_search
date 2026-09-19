"""Durable ingestion-to-AI delivery."""

from alembic import op
from modules.shared.delivery import DeliveryBase

revision = "014"
down_revision = "013"
branch_labels = depends_on = None


def upgrade():
    DeliveryBase.metadata.create_all(op.get_bind())


def downgrade():
    op.drop_table("integration_outbox")
