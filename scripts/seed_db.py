"""scripts/seed_db.py — Master seed script.

Usage:
    python scripts/seed_db.py          # Seed platform defaults only
    python scripts/seed_db.py --demo   # Seed platform defaults + demo tenant + playbooks + training + signals

Idempotent: running twice doesn't create duplicates.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

from sqlalchemy import text

from config.database import sync_engine
from core.security import hash_password
from seeds.platform_defaults import get_platform_defaults
from seeds.dormancy_taxonomy import get_dormancy_taxonomy


def seed_platform_defaults():
    """Seed platform defaults (stored as a special config record or just logged)."""
    defaults = get_platform_defaults()
    print(f"Platform defaults loaded: {len(defaults)} categories")
    print(f"  - lifecycle_thresholds: dormancy={defaults['lifecycle_thresholds']['dormancy_days']}d, at_risk={defaults['lifecycle_thresholds']['at_risk_days']}d")
    print(f"  - engagement_scoring: {list(defaults['engagement_scoring_weights'].keys())}")
    print(f"  - contact_rules: max {defaults['contact_rules']['max_contacts_per_month']}/month")
    print(f"  - TRAI hours: {defaults['trai_calling_hours']['start_hour_ist']}:00-{defaults['trai_calling_hours']['end_hour_ist']}:00 IST")
    print(f"  - rate_limits: voice={defaults['rate_limits']['voice']['max_concurrent_per_tenant']} concurrent, whatsapp={defaults['rate_limits']['whatsapp']['max_per_day_per_agent']}/day/agent")
    print("Platform defaults ready.")


def seed_dormancy_taxonomy():
    """Log dormancy taxonomy (stored in code, no DB table needed)."""
    taxonomy = get_dormancy_taxonomy()
    categories = {}
    for entry in taxonomy:
        cat = entry["parent_category"]
        categories[cat] = categories.get(cat, 0) + 1
    print(f"Dormancy taxonomy loaded: {len(taxonomy)} reasons across {len(categories)} categories")
    for cat, count in categories.items():
        print(f"  - {cat}: {count} reasons")


def seed_demo_tenant():
    """Seed the full demo tenant with users, agents, playbooks, and signals."""
    from seeds.demo_tenant import (
        DEMO_TENANT_ID,
        get_demo_tenant,
        get_demo_users,
        get_demo_agents,
    )
    from seeds.default_playbooks import get_default_playbooks

    tenant = get_demo_tenant()
    users = get_demo_users()
    agents = get_demo_agents()
    playbooks = get_default_playbooks()

    with sync_engine.begin() as conn:
        # ── Tenant ──
        existing = conn.execute(
            text("SELECT id FROM tenants WHERE id = :id"),
            {"id": str(tenant["id"])},
        ).fetchone()

        if existing:
            print(f"Demo tenant already exists: {tenant['slug']}")
            # Update config
            conn.execute(
                text("UPDATE tenants SET config = :config WHERE id = :id"),
                {"id": str(tenant["id"]), "config": json.dumps(tenant["config"])},
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                    "VALUES (:id, :name, :slug, :tier, :active, CAST(:config AS jsonb))"
                ),
                {
                    "id": str(tenant["id"]),
                    "name": tenant["name"],
                    "slug": tenant["slug"],
                    "tier": tenant["subscription_tier"],
                    "active": tenant["is_active"],
                    "config": json.dumps(tenant["config"]),
                },
            )
            print(f"Created demo tenant: {tenant['name']} ({tenant['slug']})")

        # ── Users ──
        default_password = hash_password("demo123")
        users_created = 0
        for user in users:
            existing = conn.execute(
                text("SELECT id FROM users WHERE id = :id"),
                {"id": str(user["id"])},
            ).fetchone()
            if existing:
                continue
            conn.execute(
                text(
                    "INSERT INTO users (id, tenant_id, email, full_name, phone, password_hash, roles, is_active) "
                    "VALUES (:id, :tid, :email, :name, :phone, :pw, :roles, true)"
                ),
                {
                    "id": str(user["id"]),
                    "tid": str(DEMO_TENANT_ID),
                    "email": user["email"],
                    "name": user["full_name"],
                    "phone": user.get("phone"),
                    "pw": default_password,
                    "roles": "{" + ",".join(user["roles"]) + "}",
                },
            )
            users_created += 1
        print(f"Users: {users_created} created, {len(users) - users_created} already existed")

        # ── Agents ──
        agents_created = 0
        for agent in agents:
            existing = conn.execute(
                text("SELECT id FROM agents WHERE id = :id"),
                {"id": str(agent["id"])},
            ).fetchone()
            if existing:
                continue

            conn.execute(
                text("""
                    INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, email,
                        lifecycle_state, state_since, assigned_adm_id, region_node_id,
                        preferred_language, consent_voice, consent_whatsapp,
                        engagement_score, total_policies_sold, policies_sold_last_12m,
                        dormancy_reason, license_number, license_expiry_date)
                    VALUES (:id, :tid, :code, :name, :phone, :email,
                        :state, CAST(:state_since AS timestamptz), CAST(:adm_id AS uuid), CAST(:region_id AS uuid),
                        :lang, :cv, :cw,
                        :score, :total_pol, :pol_12m,
                        :dormancy, :license_num, :license_exp)
                """),
                {
                    "id": str(agent["id"]),
                    "tid": str(DEMO_TENANT_ID),
                    "code": agent["agent_code"],
                    "name": agent["full_name"],
                    "phone": agent["phone"],
                    "email": agent.get("email"),
                    "state": agent["lifecycle_state"],
                    "state_since": agent["state_since"].isoformat(),
                    "adm_id": str(agent["assigned_adm_id"]),
                    "region_id": str(agent["region_node_id"]),
                    "lang": agent["preferred_language"],
                    "cv": agent["consent_voice"],
                    "cw": agent["consent_whatsapp"],
                    "score": agent["engagement_score"],
                    "total_pol": agent["total_policies_sold"],
                    "pol_12m": agent["policies_sold_last_12m"],
                    "dormancy": agent.get("dormancy_reason"),
                    "license_num": agent.get("license_number"),
                    "license_exp": agent.get("license_expiry_date", None),
                },
            )
            agents_created += 1

        # Count by state
        state_counts = {}
        for a in agents:
            state_counts[a["lifecycle_state"]] = state_counts.get(a["lifecycle_state"], 0) + 1
        print(f"Agents: {agents_created} created, {len(agents) - agents_created} already existed")
        for state, count in sorted(state_counts.items()):
            print(f"  - {state}: {count}")

        # ── Playbooks ──
        playbooks_created = 0
        for pb in playbooks:
            existing = conn.execute(
                text("SELECT id FROM playbooks WHERE tenant_id = :tid AND name = :name AND deleted_at IS NULL"),
                {"tid": str(DEMO_TENANT_ID), "name": pb["name"]},
            ).fetchone()
            if existing:
                continue

            pb_id = uuid.uuid4()
            conn.execute(
                text("""
                    INSERT INTO playbooks (id, tenant_id, name, description, is_active, is_default,
                        trigger_conditions, success_criteria, max_duration_days)
                    VALUES (:id, :tid, :name, :desc, true, true,
                        CAST(:triggers AS jsonb), CAST(:success AS jsonb), :max_days)
                """),
                {
                    "id": str(pb_id),
                    "tid": str(DEMO_TENANT_ID),
                    "name": pb["name"],
                    "desc": pb["description"],
                    "triggers": json.dumps(pb["trigger_conditions"]),
                    "success": json.dumps(pb["success_criteria"]),
                    "max_days": pb["max_duration_days"],
                },
            )

            for step in pb["steps"]:
                conn.execute(
                    text("""
                        INSERT INTO playbook_steps (id, playbook_id, step_number, name,
                            action_type, action_config, delay_days, next_step_rules)
                        VALUES (:id, :pb_id, :num, :name, :action, CAST(:config AS jsonb), :delay, CAST(:rules AS jsonb))
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "pb_id": str(pb_id),
                        "num": step["step_number"],
                        "name": step["name"],
                        "action": step["action_type"],
                        "config": json.dumps(step["action_config"]),
                        "delay": step["delay_days"],
                        "rules": json.dumps(step["next_step_rules"]),
                    },
                )
            playbooks_created += 1
        print(f"Playbooks: {playbooks_created} created, {len(playbooks) - playbooks_created} already existed")

    # ── Signals ──
    print("Generating simulated signals...")
    from scripts.simulate_signals import run_simulation
    run_simulation(DEMO_TENANT_ID, days=90)


def main():
    parser = argparse.ArgumentParser(description="Seed the AARS database")
    parser.add_argument("--demo", action="store_true", help="Seed demo tenant with full data")
    args = parser.parse_args()

    print("=" * 60)
    print("AARS Database Seeder")
    print("=" * 60)

    seed_platform_defaults()
    seed_dormancy_taxonomy()

    if args.demo:
        print("\n--- Seeding Demo Tenant ---")
        seed_demo_tenant()

    print("\n" + "=" * 60)
    print("Seeding complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
