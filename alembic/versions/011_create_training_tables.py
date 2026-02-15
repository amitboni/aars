"""Create training tables (Training Module)

Revision ID: 011
Revises: 010
Create Date: 2026-02-15

Tables: training_modules, training_quizzes, training_progress
RLS policies for training_modules and training_progress.
training_quizzes is NOT tenant-scoped (accessed via training_module FK).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── training_modules ──
    op.create_table(
        "training_modules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(50), nullable=False, index=True),
        sa.Column("difficulty", sa.String(20), nullable=False, server_default=sa.text("'beginner'")),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default=sa.text("'hi'")),
        sa.Column("content_type", sa.String(20), nullable=False, server_default=sa.text("'video'")),
        sa.Column("file_key", sa.String(500), nullable=True),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("thumbnail_key", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("effectiveness_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("times_assigned", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute("ALTER TABLE training_modules ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON training_modules "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    # ── training_quizzes (NOT tenant-scoped) ──
    op.create_table(
        "training_quizzes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("training_module_id", UUID(as_uuid=True), sa.ForeignKey("training_modules.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("questions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("passing_score", sa.Integer(), nullable=False, server_default=sa.text("70")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── training_progress ──
    op.create_table(
        "training_progress",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("training_module_id", UUID(as_uuid=True), sa.ForeignKey("training_modules.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'assigned'"), index=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.String(50), nullable=False, server_default=sa.text("'system'")),
        sa.Column("playbook_run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.execute("ALTER TABLE training_progress ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON training_progress "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON training_progress")
    op.drop_table("training_progress")

    op.drop_table("training_quizzes")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON training_modules")
    op.drop_table("training_modules")
