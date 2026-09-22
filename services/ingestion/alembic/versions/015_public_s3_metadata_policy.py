"""Public S3 sources and an explicit vendor metadata policy; preserve existing defaults."""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = depends_on = None


def upgrade():
    op.add_column('connectors', sa.Column('source_metadata_mode', sa.String(16), nullable=False, server_default='required'))
    op.create_check_constraint('ck_connectors_metadata_mode','connectors',"source_metadata_mode IN ('required','optional','none')")
    op.drop_constraint('ck_connectors_s3_auth_mode','connectors',type_='check')
    op.create_check_constraint('ck_connectors_s3_auth_mode','connectors',"s3_auth_mode IS NULL OR s3_auth_mode IN ('static_keys','aws_assume_role','anonymous')")


def downgrade():
    # The old constraint rejects remaining public connectors instead of silently changing their authentication.
    op.drop_constraint('ck_connectors_s3_auth_mode','connectors',type_='check')
    op.create_check_constraint('ck_connectors_s3_auth_mode','connectors',"s3_auth_mode IS NULL OR s3_auth_mode IN ('static_keys','aws_assume_role')")
    op.drop_constraint('ck_connectors_metadata_mode','connectors',type_='check')
    op.drop_column('connectors','source_metadata_mode')
