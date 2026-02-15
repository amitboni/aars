"""Create message template tables (Content Module)

Revision ID: 010
Revises: 009
Create Date: 2026-02-15

Tables: message_templates, template_usage_log
Both with RLS policies for tenant isolation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── message_templates ──
    op.create_table(
        "message_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(30), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language_variants", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("placeholders", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("buttons", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'"), index=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("previous_version_id", UUID(as_uuid=True), sa.ForeignKey("message_templates.id"), nullable=True),
        sa.Column("meta_template_id", sa.String(100), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Unique constraint: one active name+version per tenant (excluding soft-deleted)
    op.create_index(
        "ix_message_templates_tenant_name_version",
        "message_templates",
        ["tenant_id", "name", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # RLS policy for tenant isolation
    op.execute("ALTER TABLE message_templates ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON message_templates "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    # ── template_usage_log ──
    op.create_table(
        "template_usage_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("message_templates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("playbook_run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("rendered_content", sa.Text(), nullable=False),
        sa.Column("language_used", sa.String(5), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # RLS policy for template_usage_log
    op.execute("ALTER TABLE template_usage_log ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON template_usage_log "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON template_usage_log")
    op.drop_table("template_usage_log")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON message_templates")
    op.drop_index("ix_message_templates_tenant_name_version", table_name="message_templates")
    op.drop_table("message_templates")
