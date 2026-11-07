"""Add ingestion lifecycle metadata to legacy document rows."""
from alembic import op
import sqlalchemy as sa

revision = "20261107_000001"
down_revision = "20231010_123456"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("documents")}
    if "processing_error" not in columns:
        op.add_column("documents", sa.Column("processing_error", sa.Text(), nullable=True))
    if "processing_started_at" not in columns:
        op.add_column("documents", sa.Column("processing_started_at", sa.DateTime(), nullable=True))
    if "processed_at" not in columns:
        op.add_column("documents", sa.Column("processed_at", sa.DateTime(), nullable=True))
    if "ingestion_attempts" not in columns:
        op.add_column("documents", sa.Column("ingestion_attempts", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("documents", "ingestion_attempts")
    op.drop_column("documents", "processed_at")
    op.drop_column("documents", "processing_started_at")
    op.drop_column("documents", "processing_error")
