"""seeds/platform_defaults.py — Platform default configuration values.

These are sensible defaults that apply to all tenants unless overridden
in tenant.config. Seeds are idempotent — safe to run multiple times.
"""
from __future__ import annotations


LIFECYCLE_THRESHOLDS = {
    "dormancy_days": 90,
    "at_risk_days": 60,
    "active_min_policies_12m": 2,
    "productive_min_policies_12m": 6,
    "first_sale_to_active_policies": 2,
    "license_expiry_warning_days": 60,
}

ENGAGEMENT_SCORING_WEIGHTS = {
    "call_answer_rate": 0.25,
    "whatsapp_response_rate": 0.25,
    "training_completion": 0.20,
    "recency": 0.30,
}

CONTACT_RULES = {
    "min_days_between_voice_calls": 7,
    "min_days_between_whatsapp": 3,
    "max_contacts_per_month": 8,
    "max_whatsapp_per_day_per_agent": 3,
}

TRAI_CALLING_HOURS = {
    "start_hour_ist": 9,
    "end_hour_ist": 21,
    "timezone": "Asia/Kolkata",
    "applies_to": ["voice_ai"],
}

RATE_LIMITS = {
    "voice": {
        "max_concurrent_per_tenant": 5,
        "max_per_hour_per_tenant": 50,
    },
    "whatsapp": {
        "max_per_second_per_tenant": 80,
        "max_per_day_per_agent": 3,
    },
}

PLATFORM_DEFAULTS = {
    "lifecycle_thresholds": LIFECYCLE_THRESHOLDS,
    "engagement_scoring_weights": ENGAGEMENT_SCORING_WEIGHTS,
    "contact_rules": CONTACT_RULES,
    "trai_calling_hours": TRAI_CALLING_HOURS,
    "rate_limits": RATE_LIMITS,
}


def get_platform_defaults() -> dict:
    """Return the full set of platform defaults."""
    return PLATFORM_DEFAULTS.copy()


def get_default_tenant_config() -> dict:
    """Return a default tenant config with platform defaults embedded."""
    return {
        "branding": {
            "company_name": "",
            "logo_url": "",
            "primary_color": "#1a73e8",
        },
        "org_structure": {
            "hierarchy_levels": ["zone", "region", "branch", "area"],
        },
        "languages": {
            "supported": ["hi", "en", "ta", "te", "kn", "mr", "bn", "gu"],
            "default": "hi",
        },
        "lifecycle_thresholds": LIFECYCLE_THRESHOLDS,
        "engagement_scoring_weights": ENGAGEMENT_SCORING_WEIGHTS,
        "contact_rules": CONTACT_RULES,
        "trai_calling_hours": TRAI_CALLING_HOURS,
        "rate_limits": RATE_LIMITS,
        "integrations": {},
    }
