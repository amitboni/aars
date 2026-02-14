"""Create ADM Experience tables: morning_briefings, adm_actions, adm_alerts, weekly_summaries

Revision ID: 006
Revises: 005
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Morning Briefings ──────────────────────────────────────────
    op.create_table(
        "morning_briefings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("adm_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("briefing_date", sa.Date(), nullable=False),
        sa.Column("content", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_morning_briefings_adm_date", "morning_briefings", ["adm_id", "briefing_date"], unique=True)

    # ── ADM Actions ────────────────────────────────────────────────
    op.create_table(
        "adm_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("adm_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("outcome", JSONB(), nullable=True),
        sa.Column("source", sa.String(30), nullable=False, server_default="MANUAL"),
        sa.Column("nudge_reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── ADM Alerts ─────────────────────────────────────────────────
    op.create_table(
        "adm_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("adm_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("alert_type", sa.String(30), nullable=False),
        sa.Column("urgency", sa.String(10), nullable=False, server_default="MEDIUM"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acted_on_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_adm_alerts_unread", "adm_alerts", ["adm_id", "read_at"])

    # ── Weekly Summaries ───────────────────────────────────────────
    op.create_table(
        "weekly_summaries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("adm_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("content", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_weekly_summaries_adm_week", "weekly_summaries", ["adm_id", "week_start"], unique=True)

    # ── RLS Policies ───────────────────────────────────────────────
    for table in ("morning_briefings", "adm_actions", "adm_alerts", "weekly_summaries"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id')::uuid)"
        )


def downgrade() -> None:
    for table in ("weekly_summaries", "adm_alerts", "adm_actions", "morning_briefings"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)
