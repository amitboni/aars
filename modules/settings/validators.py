"""modules/settings/validators.py — Validation rules for tenant settings."""
from __future__ import annotations


SETTING_VALIDATORS: dict[str, dict] = {
    "lifecycle_thresholds": {
        "dormancy_days": {
            "type": "int",
            "min": 30,
            "max": 365,
            "description": "Days of inactivity before agent is marked dormant",
        },
        "at_risk_days": {
            "type": "int",
            "min": 14,
            "max": 180,
            "description": "Days before dormancy when agent is marked at-risk",
        },
        "active_min_policies_12m": {
            "type": "int",
            "min": 1,
            "max": 24,
            "description": "Minimum policies in 12 months to stay active",
        },
        "productive_min_policies_12m": {
            "type": "int",
            "min": 2,
            "max": 48,
            "description": "Minimum policies in 12 months to be productive",
        },
        "first_sale_to_active_policies": {
            "type": "int",
            "min": 1,
            "max": 12,
            "description": "Policies needed to transition from first_sale to active",
        },
        "license_expiry_warning_days": {
            "type": "int",
            "min": 14,
            "max": 180,
            "description": "Days before license expiry to start warnings",
        },
    },
    "engagement_scoring_weights": {
        "call_answer_rate": {
            "type": "float",
            "min": 0.0,
            "max": 1.0,
            "description": "Weight for call answer rate in engagement score",
        },
        "whatsapp_response_rate": {
            "type": "float",
            "min": 0.0,
            "max": 1.0,
            "description": "Weight for WhatsApp response rate",
        },
        "training_completion": {
            "type": "float",
            "min": 0.0,
            "max": 1.0,
            "description": "Weight for training completion",
        },
        "recency": {
            "type": "float",
            "min": 0.0,
            "max": 1.0,
            "description": "Weight for recency of activity",
        },
    },
    "contact_rules": {
        "min_days_between_voice_calls": {
            "type": "int",
            "min": 1,
            "max": 30,
            "description": "Minimum days between voice calls to same agent",
        },
        "min_days_between_whatsapp": {
            "type": "int",
            "min": 1,
            "max": 14,
            "description": "Minimum days between WhatsApp messages",
        },
        "max_contacts_per_month": {
            "type": "int",
            "min": 1,
            "max": 30,
            "description": "Maximum total contacts per agent per month",
        },
        "max_whatsapp_per_day_per_agent": {
            "type": "int",
            "min": 1,
            "max": 10,
            "description": "Maximum WhatsApp messages per agent per day",
        },
    },
    "trai_calling_hours": {
        "start_hour_ist": {
            "type": "int",
            "min": 8,
            "max": 12,
            "description": "Earliest calling hour IST",
        },
        "end_hour_ist": {
            "type": "int",
            "min": 18,
            "max": 21,
            "description": "Latest calling hour IST",
        },
    },
    "rate_limits": {
        "voice.max_concurrent_per_tenant": {
            "type": "int",
            "min": 1,
            "max": 50,
            "description": "Max concurrent voice calls",
        },
        "voice.max_per_hour_per_tenant": {
            "type": "int",
            "min": 10,
            "max": 500,
            "description": "Max voice calls per hour",
        },
        "whatsapp.max_per_second_per_tenant": {
            "type": "int",
            "min": 10,
            "max": 1000,
            "description": "Max WhatsApp messages per second",
        },
        "whatsapp.max_per_day_per_agent": {
            "type": "int",
            "min": 1,
            "max": 10,
            "description": "Max WhatsApp per agent per day",
        },
    },
    "branding": {
        "company_name": {
            "type": "str",
            "max_length": 200,
            "description": "Company display name",
        },
        "logo_url": {
            "type": "str",
            "max_length": 500,
            "description": "Company logo URL",
        },
    },
    "languages": {
        "supported": {
            "type": "list",
            "allowed_values": [
                "hi", "en", "ta", "te", "kn", "mr", "bn", "ml", "gu", "pa", "or", "as",
            ],
            "description": "Supported languages",
        },
        "default": {
            "type": "str",
            "allowed_values": [
                "hi", "en", "ta", "te", "kn", "mr", "bn", "ml", "gu", "pa", "or", "as",
            ],
            "description": "Default language",
        },
    },
}

VALID_SECTIONS = list(SETTING_VALIDATORS.keys())


def _resolve_nested_value(data: dict, dotted_key: str):
    """Resolve a dotted key like 'voice.max_concurrent_per_tenant' into nested dict access."""
    parts = dotted_key.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested_value(data: dict, dotted_key: str, value) -> dict:
    """Set a value in a nested dict using a dotted key. Returns mutated dict."""
    parts = dotted_key.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value
    return data


def validate_section_changes(
    section: str, proposed: dict, current: dict
) -> list[str]:
    """Validate proposed changes for a settings section.

    Args:
        section: Settings section name (e.g. 'lifecycle_thresholds').
        proposed: Dict of {field: new_value} being changed.
        current: Dict of current values for the entire section.

    Returns:
        List of error strings. Empty = valid.
    """
    if section not in SETTING_VALIDATORS:
        return [f"Unknown settings section: '{section}'"]

    validators = SETTING_VALIDATORS[section]
    errors: list[str] = []

    # Check for unknown fields
    for field in proposed:
        # For rate_limits, proposed may use dotted keys or nested dicts
        if section == "rate_limits" and isinstance(proposed[field], dict):
            # Nested dict like {"voice": {"max_concurrent_per_tenant": 10}}
            for subfield_key, subfield_val in proposed[field].items():
                dotted = f"{field}.{subfield_key}"
                if dotted not in validators:
                    errors.append(f"Unknown field '{dotted}' in section '{section}'")
        else:
            if field not in validators:
                errors.append(f"Unknown field '{field}' in section '{section}'")

    # Validate each proposed field
    for field, value in proposed.items():
        if section == "rate_limits" and isinstance(value, dict):
            for subfield_key, subfield_val in value.items():
                dotted = f"{field}.{subfield_key}"
                if dotted in validators:
                    errs = _validate_field(dotted, subfield_val, validators[dotted])
                    errors.extend(errs)
        elif field in validators:
            errs = _validate_field(field, value, validators[field])
            errors.extend(errs)

    if errors:
        return errors

    # Cross-field validations on merged values
    merged = {**current, **proposed}

    if section == "engagement_scoring_weights":
        errors.extend(_cross_validate_weights(merged))
    elif section == "trai_calling_hours":
        errors.extend(_cross_validate_trai_hours(merged))
    elif section == "contact_rules":
        errors.extend(_cross_validate_contact_rules(merged))
    elif section == "lifecycle_thresholds":
        errors.extend(_cross_validate_lifecycle(merged))

    return errors


def _validate_field(field: str, value, rules: dict) -> list[str]:
    """Validate a single field against its rules."""
    errors: list[str] = []
    expected_type = rules["type"]

    if expected_type == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"'{field}' must be an integer, got {type(value).__name__}")
            return errors
        if "min" in rules and value < rules["min"]:
            errors.append(f"'{field}' must be between {rules['min']} and {rules['max']}")
        if "max" in rules and value > rules["max"]:
            errors.append(f"'{field}' must be between {rules['min']} and {rules['max']}")

    elif expected_type == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"'{field}' must be a number, got {type(value).__name__}")
            return errors
        value = float(value)
        if "min" in rules and value < rules["min"]:
            errors.append(f"'{field}' must be between {rules['min']} and {rules['max']}")
        if "max" in rules and value > rules["max"]:
            errors.append(f"'{field}' must be between {rules['min']} and {rules['max']}")

    elif expected_type == "str":
        if not isinstance(value, str):
            errors.append(f"'{field}' must be a string, got {type(value).__name__}")
            return errors
        if "max_length" in rules and len(value) > rules["max_length"]:
            errors.append(f"'{field}' exceeds maximum length of {rules['max_length']}")
        if "allowed_values" in rules and value not in rules["allowed_values"]:
            errors.append(f"'{field}' must be one of: {rules['allowed_values']}")

    elif expected_type == "list":
        if not isinstance(value, list):
            errors.append(f"'{field}' must be a list, got {type(value).__name__}")
            return errors
        if "allowed_values" in rules:
            for item in value:
                if item not in rules["allowed_values"]:
                    errors.append(
                        f"'{field}' contains invalid value '{item}'. "
                        f"Allowed: {rules['allowed_values']}"
                    )

    return errors


def _cross_validate_weights(merged: dict) -> list[str]:
    """All engagement scoring weights must sum to 1.0 (tolerance 0.01)."""
    weight_fields = ["call_answer_rate", "whatsapp_response_rate", "training_completion", "recency"]
    total = sum(float(merged.get(f, 0)) for f in weight_fields)
    if abs(total - 1.0) > 0.01:
        return [f"Engagement scoring weights must sum to 1.0 (currently {total:.4f})"]
    return []


def _cross_validate_trai_hours(merged: dict) -> list[str]:
    """start_hour_ist must be strictly less than end_hour_ist."""
    start = merged.get("start_hour_ist")
    end = merged.get("end_hour_ist")
    if start is not None and end is not None and start >= end:
        return [f"start_hour_ist ({start}) must be less than end_hour_ist ({end})"]
    return []


def _cross_validate_contact_rules(merged: dict) -> list[str]:
    """max_contacts_per_month must be >= max_whatsapp_per_day_per_agent."""
    max_contacts = merged.get("max_contacts_per_month")
    max_wa = merged.get("max_whatsapp_per_day_per_agent")
    if max_contacts is not None and max_wa is not None and max_contacts < max_wa:
        return [
            f"max_contacts_per_month ({max_contacts}) must be >= "
            f"max_whatsapp_per_day_per_agent ({max_wa})"
        ]
    return []


def _cross_validate_lifecycle(merged: dict) -> list[str]:
    """at_risk_days must be strictly less than dormancy_days."""
    at_risk = merged.get("at_risk_days")
    dormancy = merged.get("dormancy_days")
    if at_risk is not None and dormancy is not None and at_risk >= dormancy:
        return [
            f"at_risk_days ({at_risk}) must be strictly less than dormancy_days ({dormancy})"
        ]
    return []


def get_section_metadata(section: str) -> dict | None:
    """Return validation metadata for a section's fields."""
    validators = SETTING_VALIDATORS.get(section)
    if not validators:
        return None
    return {field: {**rules} for field, rules in validators.items()}
