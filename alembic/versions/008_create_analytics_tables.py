"""Create analytics tables (Slice 8)

Revision ID: 008
Revises: 007
Create Date: 2026-02-14

Three tables: analytics_snapshots, reactivation_funnels, dormancy_analytics
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── analytics_snapshots ───
    op.create_table(
        "analytics_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False, index=True),
        sa.Column("snapshot_type", sa.String(20), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_analytics_snapshots_tenant_date_type",
        "analytics_snapshots",
        ["tenant_id", "snapshot_date", "snapshot_type"],
        unique=True,
    )
    op.execute("ALTER TABLE analytics_snapshots ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON analytics_snapshots "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    # ─── reactivation_funnels ───
    op.create_table(
        "reactivation_funnels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("period_start", sa.Date(), nullable=False, index=True),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("contacted_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("engaged_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("trained_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sold_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("funnel_by_channel", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("funnel_by_playbook", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_reactivation_funnels_tenant_period",
        "reactivation_funnels",
        ["tenant_id", "period_start"],
        unique=True,
    )
    op.execute("ALTER TABLE reactivation_funnels ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON reactivation_funnels "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    # ─── dormancy_analytics ───
    op.create_table(
        "dormancy_analytics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False, index=True),
        sa.Column("reason_distribution", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trend_vs_previous", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("regional_breakdown", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_dormancy_analytics_tenant_date",
        "dormancy_analytics",
        ["tenant_id", "snapshot_date"],
        unique=True,
    )
    op.execute("ALTER TABLE dormancy_analytics ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON dormancy_analytics "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON dormancy_analytics")
    op.drop_table("dormancy_analytics")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON reactivation_funnels")
    op.drop_table("reactivation_funnels")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON analytics_snapshots")
    op.drop_table("analytics_snapshots")
