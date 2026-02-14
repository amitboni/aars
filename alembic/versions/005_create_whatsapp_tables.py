"""Create WhatsApp conversation tracking and message log tables

Revision ID: 005
Revises: 004
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── WhatsApp Message Log ──────────────────────────────────────────
    op.create_table(
        "whatsapp_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("direction", sa.String(10), nullable=False),  # inbound, outbound
        sa.Column("message_type", sa.String(30), nullable=False),  # text, template, interactive, media
        sa.Column("wamid", sa.String(200), nullable=True),  # Meta's message ID
        sa.Column("template_name", sa.String(100), nullable=True),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="sent"),  # sent, delivered, read, failed
        sa.Column("from_phone", sa.String(20), nullable=True),
        sa.Column("to_phone", sa.String(20), nullable=True),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("error_code", sa.String(20), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_whatsapp_messages_wamid", "whatsapp_messages", ["wamid"])
    op.create_index("ix_whatsapp_messages_tenant_agent", "whatsapp_messages", ["tenant_id", "agent_id"])

    # ── WhatsApp Conversation Tracking ────────────────────────────────
    # Tracks the 24-hour conversation window for free-form messaging
    op.create_table(
        "whatsapp_conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("agent_phone", sa.String(20), nullable=False),
        sa.Column("window_open_at", sa.DateTime(timezone=True), nullable=False),  # When agent last replied
        sa.Column("window_close_at", sa.DateTime(timezone=True), nullable=False),  # 24h after agent reply
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_whatsapp_conversations_active", "whatsapp_conversations", ["tenant_id", "agent_id", "is_active"])

    # ── Training Quiz State ───────────────────────────────────────────
    # Persists quiz progress (survives server restarts)
    op.create_table(
        "whatsapp_quiz_states",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("module_id", sa.String(100), nullable=False),
        sa.Column("module_name", sa.String(200), nullable=False),
        sa.Column("current_question", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("answers", JSONB(), nullable=True),  # List of answer indices
        sa.Column("questions", JSONB(), nullable=False),  # Quiz questions snapshot
        sa.Column("score_percent", sa.Float(), nullable=True),
        sa.Column("is_complete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_whatsapp_quiz_active", "whatsapp_quiz_states", ["tenant_id", "agent_id", "is_complete"])

    # ── RLS Policies ──────────────────────────────────────────────────
    for table in ("whatsapp_messages", "whatsapp_conversations", "whatsapp_quiz_states"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id')::uuid)"
        )


def downgrade() -> None:
    for table in ("whatsapp_quiz_states", "whatsapp_conversations", "whatsapp_messages"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)
