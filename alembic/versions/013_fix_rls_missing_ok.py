"""Fix RLS policies to use missing_ok and support no-tenant bypass

On Render's shared Postgres the DB user is not the table owner,
so RLS policies are enforced even for the application user.
current_setting('app.tenant_id') without missing_ok crashes when
the setting isn't set (e.g. login endpoint via get_db_no_tenant).

This migration updates ALL tenant_isolation policies to:
1. Use current_setting('app.tenant_id', true) so NULL is returned
   instead of an error when the setting doesn't exist.
2. Check current_setting('app.rls_bypass', true) = 'true' to allow
   no-tenant sessions (login) to query across tenants.

Revision ID: 013
Revises: 012
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table that has a tenant_isolation RLS policy
TABLES_WITH_RLS = [
    "users",
    "agents",
    "playbooks",
    "playbook_runs",
    "whatsapp_messages",
    "whatsapp_conversations",
    "whatsapp_quiz_states",
    "morning_briefings",
    "adm_actions",
    "adm_alerts",
    "weekly_summaries",
    "decision_logs",
    "analytics_snapshots",
    "reactivation_funnels",
    "dormancy_analytics",
    "integration_jobs",
    "message_templates",
    "template_usage_log",
    "training_modules",
    "training_progress",
    "settings_change_requests",
    "settings_audit_log",
]

NEW_POLICY = (
    "CREATE POLICY tenant_isolation ON {table} "
    "USING ("
    "current_setting('app.rls_bypass', true) = 'true' "
    "OR tenant_id = current_setting('app.tenant_id', true)::uuid"
    ")"
)

OLD_POLICY = (
    "CREATE POLICY tenant_isolation ON {table} "
    "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
)


def upgrade() -> None:
    for table in TABLES_WITH_RLS:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(NEW_POLICY.format(table=table))


def downgrade() -> None:
    for table in TABLES_WITH_RLS:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(OLD_POLICY.format(table=table))
