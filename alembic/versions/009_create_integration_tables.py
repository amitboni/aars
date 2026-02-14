"""Create integration tables (Slice 9)

Revision ID: 009
Revises: 008
Create Date: 2026-02-14

One table: integration_jobs with RLS policy.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_type", sa.String(30), nullable=False, index=True),
        sa.Column("source_system", sa.String(30), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processed_records", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_records", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("errors", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # RLS policy for tenant isolation
    op.execute("ALTER TABLE integration_jobs ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON integration_jobs "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON integration_jobs")
    op.drop_table("integration_jobs")
