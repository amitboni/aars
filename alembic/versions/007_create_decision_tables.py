"""Create decision_logs table for Decision Engine (Slice 7)

Revision ID: 007
Revises: 006
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "decision_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("adm_id", UUID(as_uuid=True), nullable=True),
        sa.Column("rule_id", sa.String(50), nullable=False),
        sa.Column("decision_action", sa.String(50), nullable=False),
        sa.Column("playbook_id", UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("language", sa.String(5), nullable=True),
        sa.Column("priority", sa.String(10), nullable=False, server_default="MEDIUM"),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("scheduled_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_result", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Composite indexes for common queries
    op.create_index("ix_decision_logs_agent_created", "decision_logs", ["agent_id", "created_at"])
    op.create_index("ix_decision_logs_pending", "decision_logs", ["executed", "scheduled_time"])

    # RLS
    op.execute("ALTER TABLE decision_logs ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON decision_logs "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON decision_logs")
    op.drop_table("decision_logs")
