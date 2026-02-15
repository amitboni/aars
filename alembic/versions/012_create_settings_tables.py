"""Create settings tables (Settings Change Requests, Audit Log)

Revision ID: 012
Revises: 011
Create Date: 2026-02-15

Tables: settings_change_requests, settings_audit_log
RLS policies for both tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── settings_change_requests ──
    op.create_table(
        "settings_change_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("requested_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section", sa.String(50), nullable=False, index=True),
        sa.Column("current_values", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("proposed_values", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending_otp'"), index=True),
        sa.Column("otp_hash", sa.String(128), nullable=False),
        sa.Column("otp_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("otp_sent_to", sa.String(255), nullable=False),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.execute("ALTER TABLE settings_change_requests ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON settings_change_requests "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    # ── settings_audit_log ──
    op.create_table(
        "settings_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("change_request_id", UUID(as_uuid=True), sa.ForeignKey("settings_change_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changed_by_email", sa.String(255), nullable=False),
        sa.Column("section", sa.String(50), nullable=False, index=True),
        sa.Column("previous_values", JSONB(), nullable=False),
        sa.Column("new_values", JSONB(), nullable=False),
        sa.Column("changed_fields", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.execute("ALTER TABLE settings_audit_log ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON settings_audit_log "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON settings_audit_log")
    op.drop_table("settings_audit_log")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON settings_change_requests")
    op.drop_table("settings_change_requests")
