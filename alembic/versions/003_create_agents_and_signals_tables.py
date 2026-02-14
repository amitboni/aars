"""Create agents and signals tables

Revision ID: 003
Revises: 002
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Agents table ─────────────────────────────────────────────────────
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_code", sa.String(50), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(15), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("lifecycle_state", sa.String(30), nullable=False, server_default="onboarded", index=True),
        sa.Column("state_since", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("assigned_adm_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("engagement_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_positive_signal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_policies_sold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("policies_sold_last_12m", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dormancy_reason", sa.String(100), nullable=True),
        sa.Column("license_number", sa.String(50), nullable=True),
        sa.Column("license_expiry_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_voice", sa.String(20), nullable=False, server_default="not_asked"),
        sa.Column("consent_whatsapp", sa.String(20), nullable=False, server_default="not_asked"),
        sa.Column("preferred_language", sa.String(5), nullable=False, server_default="hi"),
        sa.Column("region_node_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Unique agent_code per tenant (only for non-deleted agents)
    op.create_index(
        "ix_agents_tenant_code_unique",
        "agents",
        ["tenant_id", "agent_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # RLS policy for agents (uses TenantScopedMixin)
    op.execute("ALTER TABLE agents ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON agents "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    # ── Signals table ────────────────────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("signal_type", sa.String(100), nullable=False, index=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("adm_id", UUID(as_uuid=True), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Unique idempotency_key per tenant (only when key is not null)
    op.create_index(
        "ix_signals_tenant_idempotency",
        "signals",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # Index for slow path: unprocessed signals
    op.create_index(
        "ix_signals_unprocessed",
        "signals",
        ["processed", "created_at"],
        postgresql_where=sa.text("processed = false"),
    )

    # Composite index for agent signal history queries
    op.create_index(
        "ix_signals_agent_timestamp",
        "signals",
        ["agent_id", "timestamp"],
    )

    # NOTE: signals table does NOT use RLS (per CLAUDE.md, for performance reasons).
    # Tenant filtering is done at the service layer.


def downgrade() -> None:
    # Drop signals indexes and table
    op.drop_index("ix_signals_agent_timestamp", table_name="signals")
    op.drop_index("ix_signals_unprocessed", table_name="signals")
    op.drop_index("ix_signals_tenant_idempotency", table_name="signals")
    op.drop_table("signals")

    # Drop agents RLS, indexes, and table
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON agents")
    op.execute("ALTER TABLE agents DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_agents_tenant_code_unique", table_name="agents")
    op.drop_table("agents")
