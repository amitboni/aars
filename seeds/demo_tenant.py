"""seeds/demo_tenant.py — Create a complete demo tenant with realistic data.

Creates:
- 1 Tenant "Demo Insurance Co" with full config
- Region hierarchy: 1 Zone → 2 Regions → 4 Branches → 8 Areas
- 5 ADM users (various archetypes)
- 50 agents across all lifecycle states with realistic diversity
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from seeds.platform_defaults import get_default_tenant_config

# Fixed UUIDs for idempotency (running twice won't create duplicates)
DEMO_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEMO_TENANT_SLUG = "demo-insurance-co"

# ── Region Hierarchy ────────────────────────────────────────────────────

ZONE_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
REGION_IDS = [
    uuid.UUID("20000000-0000-0000-0000-000000000001"),
    uuid.UUID("20000000-0000-0000-0000-000000000002"),
]
BRANCH_IDS = [
    uuid.UUID("30000000-0000-0000-0000-000000000001"),
    uuid.UUID("30000000-0000-0000-0000-000000000002"),
    uuid.UUID("30000000-0000-0000-0000-000000000003"),
    uuid.UUID("30000000-0000-0000-0000-000000000004"),
]
AREA_IDS = [
    uuid.UUID(f"40000000-0000-0000-0000-00000000000{i}") for i in range(1, 9)
]


def _build_region_hierarchy() -> dict:
    """Build org_structure config for the demo tenant."""
    return {
        "hierarchy_levels": ["zone", "region", "branch", "area"],
        "nodes": [
            {"id": str(ZONE_ID), "name": "North Zone", "level": "zone", "parent_id": None},
            {"id": str(REGION_IDS[0]), "name": "Delhi Region", "level": "region", "parent_id": str(ZONE_ID)},
            {"id": str(REGION_IDS[1]), "name": "Punjab Region", "level": "region", "parent_id": str(ZONE_ID)},
            {"id": str(BRANCH_IDS[0]), "name": "New Delhi Branch", "level": "branch", "parent_id": str(REGION_IDS[0])},
            {"id": str(BRANCH_IDS[1]), "name": "Noida Branch", "level": "branch", "parent_id": str(REGION_IDS[0])},
            {"id": str(BRANCH_IDS[2]), "name": "Chandigarh Branch", "level": "branch", "parent_id": str(REGION_IDS[1])},
            {"id": str(BRANCH_IDS[3]), "name": "Ludhiana Branch", "level": "branch", "parent_id": str(REGION_IDS[1])},
            {"id": str(AREA_IDS[0]), "name": "Connaught Place", "level": "area", "parent_id": str(BRANCH_IDS[0])},
            {"id": str(AREA_IDS[1]), "name": "Karol Bagh", "level": "area", "parent_id": str(BRANCH_IDS[0])},
            {"id": str(AREA_IDS[2]), "name": "Sector 18", "level": "area", "parent_id": str(BRANCH_IDS[1])},
            {"id": str(AREA_IDS[3]), "name": "Sector 62", "level": "area", "parent_id": str(BRANCH_IDS[1])},
            {"id": str(AREA_IDS[4]), "name": "Sector 17", "level": "area", "parent_id": str(BRANCH_IDS[2])},
            {"id": str(AREA_IDS[5]), "name": "Industrial Area", "level": "area", "parent_id": str(BRANCH_IDS[2])},
            {"id": str(AREA_IDS[6]), "name": "Civil Lines", "level": "area", "parent_id": str(BRANCH_IDS[3])},
            {"id": str(AREA_IDS[7]), "name": "Sarabha Nagar", "level": "area", "parent_id": str(BRANCH_IDS[3])},
        ],
    }


# ── ADM Users ───────────────────────────────────────────────────────────

ADM_DATA = [
    {
        "id": uuid.UUID("50000000-0000-0000-0000-000000000001"),
        "email": "adm.sharma@demo-insurance.co",
        "full_name": "Rajesh Sharma",
        "phone": "9810000001",
        "roles": ["adm"],
        "archetype": "HIGH_PERFORMER",
    },
    {
        "id": uuid.UUID("50000000-0000-0000-0000-000000000002"),
        "email": "adm.singh@demo-insurance.co",
        "full_name": "Gurpreet Singh",
        "phone": "9810000002",
        "roles": ["adm"],
        "archetype": "AVERAGE",
    },
    {
        "id": uuid.UUID("50000000-0000-0000-0000-000000000003"),
        "email": "adm.verma@demo-insurance.co",
        "full_name": "Priya Verma",
        "phone": "9810000003",
        "roles": ["adm"],
        "archetype": "AVERAGE",
    },
    {
        "id": uuid.UUID("50000000-0000-0000-0000-000000000004"),
        "email": "adm.kumar@demo-insurance.co",
        "full_name": "Sunil Kumar",
        "phone": "9810000004",
        "roles": ["adm"],
        "archetype": "STRUGGLING",
    },
    {
        "id": uuid.UUID("50000000-0000-0000-0000-000000000005"),
        "email": "adm.gupta@demo-insurance.co",
        "full_name": "Anita Gupta",
        "phone": "9810000005",
        "roles": ["adm"],
        "archetype": "UNRESPONSIVE",
    },
]

# Tenant admin user
ADMIN_USER = {
    "id": uuid.UUID("50000000-0000-0000-0000-000000000099"),
    "email": "admin@demo-insurance.co",
    "full_name": "Demo Admin",
    "phone": "9810000099",
    "roles": ["tenant_admin"],
}


# ── 50 Agents ───────────────────────────────────────────────────────────

_NOW = datetime.now(timezone.utc)
_NAMES = [
    # Hindi/North Indian names
    ("Amit", "Sharma"), ("Rakesh", "Kumar"), ("Sunita", "Devi"), ("Vijay", "Yadav"),
    ("Meena", "Gupta"), ("Ravi", "Tiwari"), ("Pooja", "Singh"), ("Deepak", "Verma"),
    ("Neha", "Agarwal"), ("Ajay", "Chauhan"), ("Priya", "Joshi"), ("Manoj", "Pandey"),
    ("Kavita", "Mishra"), ("Rahul", "Saxena"), ("Suman", "Rawat"), ("Arun", "Thakur"),
    ("Anita", "Negi"), ("Rajesh", "Bisht"), ("Seema", "Pant"), ("Suresh", "Bhatt"),
    ("Geeta", "Nautiyal"), ("Mohit", "Dimri"), ("Sapna", "Jha"), ("Vikram", "Sinha"),
    ("Rina", "Banerjee"), ("Pankaj", "Das"), ("Swati", "Bose"), ("Abhishek", "Roy"),
    ("Nisha", "Ghosh"), ("Dinesh", "Mukherjee"), ("Aarti", "Chatterjee"), ("Sanjay", "Sen"),
    ("Manju", "Mazumdar"), ("Vivek", "Pal"), ("Ritu", "Talwar"), ("Gaurav", "Malhotra"),
    ("Kamla", "Kapoor"), ("Nitin", "Dhawan"), ("Reena", "Bhatia"), ("Harsh", "Mehra"),
    ("Usha", "Grover"), ("Yogesh", "Chawla"), ("Shilpa", "Kohli"), ("Anil", "Sethi"),
    ("Pushpa", "Arora"), ("Lokesh", "Khanna"), ("Madhu", "Tandon"), ("Tarun", "Oberoi"),
    ("Kusum", "Wadhwa"), ("Hemant", "Khurana"),
]

_LANGUAGES = ["hi", "hi", "hi", "en", "hi", "ta", "te", "kn", "mr", "bn", "gu", "hi", "en"]
_CONSENT_OPTIONS = ["granted", "granted", "granted", "not_asked", "denied"]

# Dormancy reasons for the 15 DORMANT agents
_DORMANCY_REASONS = [
    "training_gap.product_knowledge_insufficient",
    "training_gap.sales_skills_lacking",
    "training_gap.process_unclear",
    "economic.commission_too_low",
    "economic.competitor_better_commission",
    "engagement_gap.feels_unsupported",
    "engagement_gap.adm_never_contacted",
    "operational.proposal_process_complex",
    "operational.technology_barriers",
    "personal.lost_interest",
    "personal.other_employment",
    "personal.family_obligations",
    "regulatory.license_expiring_soon",
    "economic.insufficient_income",
    "unknown",
]


def _make_agents() -> list[dict]:
    """Build 50 agent records across all lifecycle states."""
    agents = []
    agent_idx = 0

    def _agent(state: str, extra: dict | None = None) -> dict:
        nonlocal agent_idx
        first, last = _NAMES[agent_idx]
        adm_idx = agent_idx % 5
        area_idx = agent_idx % 8

        data = {
            "id": uuid.UUID(f"60000000-0000-0000-0000-{agent_idx + 1:012d}"),
            "agent_code": f"AG{agent_idx + 1:04d}",
            "full_name": f"{first} {last}",
            "phone": f"98{10000100 + agent_idx}",
            "email": f"{first.lower()}.{last.lower()}@example.com",
            "lifecycle_state": state,
            "state_since": _NOW - timedelta(days=30 + agent_idx * 2),
            "assigned_adm_id": ADM_DATA[adm_idx]["id"],
            "region_node_id": AREA_IDS[area_idx],
            "preferred_language": _LANGUAGES[agent_idx % len(_LANGUAGES)],
            "consent_voice": _CONSENT_OPTIONS[agent_idx % len(_CONSENT_OPTIONS)],
            "consent_whatsapp": "granted" if agent_idx % 4 != 3 else "not_asked",
            "engagement_score": 0.0,
            "total_policies_sold": 0,
            "policies_sold_last_12m": 0,
        }

        if extra:
            data.update(extra)
        agent_idx += 1
        return data

    # 5 ONBOARDED (recent, no exam yet)
    for i in range(5):
        agents.append(_agent("onboarded", {
            "state_since": _NOW - timedelta(days=5 + i * 3),
            "engagement_score": 10.0 + i * 5,
        }))

    # 5 LICENSED (passed exam, no sale)
    for i in range(5):
        agents.append(_agent("licensed", {
            "state_since": _NOW - timedelta(days=20 + i * 5),
            "license_number": f"IRDAI-2024-{1000 + i}",
            "engagement_score": 30.0 + i * 5,
        }))

    # 3 FIRST_SALE (just made first sale)
    for i in range(3):
        agents.append(_agent("first_sale", {
            "state_since": _NOW - timedelta(days=3 + i),
            "total_policies_sold": 1,
            "policies_sold_last_12m": 1,
            "last_positive_signal_at": _NOW - timedelta(days=i + 1),
            "engagement_score": 55.0 + i * 5,
        }))

    # 8 ACTIVE (regular selling)
    for i in range(8):
        policies = 3 + i
        agents.append(_agent("active", {
            "state_since": _NOW - timedelta(days=60 + i * 10),
            "total_policies_sold": policies,
            "policies_sold_last_12m": policies,
            "last_positive_signal_at": _NOW - timedelta(days=i * 3 + 1),
            "last_contact_at": _NOW - timedelta(days=i * 2),
            "engagement_score": 60.0 + i * 3,
        }))

    # 4 PRODUCTIVE (exceeding targets)
    for i in range(4):
        policies = 10 + i * 3
        agents.append(_agent("productive", {
            "state_since": _NOW - timedelta(days=90 + i * 15),
            "total_policies_sold": policies,
            "policies_sold_last_12m": policies - 2,
            "last_positive_signal_at": _NOW - timedelta(days=i + 1),
            "last_contact_at": _NOW - timedelta(days=i * 5),
            "engagement_score": 80.0 + i * 4,
        }))

    # 5 AT_RISK (declining signals)
    for i in range(5):
        agents.append(_agent("at_risk", {
            "state_since": _NOW - timedelta(days=15 + i * 5),
            "total_policies_sold": 2 + i,
            "policies_sold_last_12m": 1,
            "last_positive_signal_at": _NOW - timedelta(days=35 + i * 10),
            "last_contact_at": _NOW - timedelta(days=20 + i * 5),
            "engagement_score": 25.0 - i * 3,
        }))

    # 15 DORMANT (various dormancy reasons)
    for i in range(15):
        agents.append(_agent("dormant", {
            "state_since": _NOW - timedelta(days=60 + i * 10),
            "dormancy_reason": _DORMANCY_REASONS[i],
            "total_policies_sold": i % 4,
            "policies_sold_last_12m": 0,
            "last_positive_signal_at": _NOW - timedelta(days=90 + i * 5),
            "last_contact_at": _NOW - timedelta(days=60 + i * 5) if i % 3 != 0 else None,
            "engagement_score": max(0.0, 15.0 - i * 1.5),
        }))

    # 3 LAPSED (license expired)
    for i in range(3):
        agents.append(_agent("lapsed", {
            "state_since": _NOW - timedelta(days=30 + i * 10),
            "license_number": f"IRDAI-2022-{2000 + i}",
            "license_expiry_date": _NOW - timedelta(days=10 + i * 5),
            "total_policies_sold": 1 + i,
            "engagement_score": 5.0,
        }))

    # 2 TERMINATED
    for i in range(2):
        agents.append(_agent("terminated", {
            "state_since": _NOW - timedelta(days=60 + i * 30),
            "total_policies_sold": i,
            "engagement_score": 0.0,
        }))

    return agents


def get_demo_tenant_config() -> dict:
    """Return full tenant config for the demo tenant."""
    config = get_default_tenant_config()
    config["branding"] = {
        "company_name": "Demo Insurance Co",
        "logo_url": "https://example.com/demo-logo.png",
        "primary_color": "#2e7d32",
    }
    config["org_structure"] = _build_region_hierarchy()
    config["lifecycle_thresholds"]["dormancy_days"] = 90
    config["lifecycle_thresholds"]["at_risk_days"] = 60
    config["engagement_scoring_weights"] = {
        "call_answer_rate": 0.25,
        "whatsapp_response_rate": 0.25,
        "training_completion": 0.20,
        "recency": 0.30,
    }
    return config


def get_demo_tenant() -> dict:
    """Return demo tenant record."""
    return {
        "id": DEMO_TENANT_ID,
        "name": "Demo Insurance Co",
        "slug": DEMO_TENANT_SLUG,
        "subscription_tier": "enterprise",
        "is_active": True,
        "config": get_demo_tenant_config(),
    }


def get_demo_users() -> list[dict]:
    """Return ADM users + admin user."""
    users = [ADMIN_USER]
    users.extend(ADM_DATA)
    return users


def get_demo_agents() -> list[dict]:
    """Return 50 demo agents."""
    return _make_agents()
