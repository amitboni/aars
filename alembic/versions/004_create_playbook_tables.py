"""Create playbook tables

Revision ID: 004
Revises: 003
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Playbooks table (definitions) ────────────────────────────────
    op.create_table(
        "playbooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("trigger_conditions", JSONB, nullable=False, server_default="{}"),
        sa.Column("success_criteria", JSONB, nullable=False, server_default="{}"),
        sa.Column("max_duration_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("times_executed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Unique name per tenant (non-deleted)
    op.create_index(
        "ix_playbooks_tenant_name_unique",
        "playbooks",
        ["tenant_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # RLS for playbooks
    op.execute("ALTER TABLE playbooks ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON playbooks "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    # ── Playbook steps table ─────────────────────────────────────────
    op.create_table(
        "playbook_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("playbook_id", UUID(as_uuid=True), sa.ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("action_config", JSONB, nullable=False, server_default="{}"),
        sa.Column("delay_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_step_rules", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Unique step_number per playbook
    op.create_index(
        "ix_playbook_steps_playbook_step",
        "playbook_steps",
        ["playbook_id", "step_number"],
        unique=True,
    )

    # ── Playbook runs table (execution instances) ────────────────────
    op.create_table(
        "playbook_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("playbook_id", UUID(as_uuid=True), sa.ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="in_progress"),
        sa.Column("current_step_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("context", JSONB, nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_step_due_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("outcome", sa.String(50), nullable=True),
        sa.Column("steps_executed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Index for Celery beat: find runs with due steps
    op.create_index(
        "ix_playbook_runs_due_steps",
        "playbook_runs",
        ["status", "next_step_due_at"],
        postgresql_where=sa.text("status = 'in_progress' AND next_step_due_at IS NOT NULL"),
    )

    # RLS for playbook_runs
    op.execute("ALTER TABLE playbook_runs ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON playbook_runs "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    # ── Playbook step runs table (step execution tracking) ───────────
    op.create_table(
        "playbook_step_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("playbook_run_id", UUID(as_uuid=True), sa.ForeignKey("playbook_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("playbook_step_id", UUID(as_uuid=True), sa.ForeignKey("playbook_steps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(100), nullable=True),
        sa.Column("outcome_details", JSONB, nullable=False, server_default="{}"),
        sa.Column("next_step_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("playbook_step_runs")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON playbook_runs")
    op.execute("ALTER TABLE playbook_runs DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_playbook_runs_due_steps", table_name="playbook_runs")
    op.drop_table("playbook_runs")

    op.drop_index("ix_playbook_steps_playbook_step", table_name="playbook_steps")
    op.drop_table("playbook_steps")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON playbooks")
    op.execute("ALTER TABLE playbooks DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_playbooks_tenant_name_unique", table_name="playbooks")
    op.drop_table("playbooks")
