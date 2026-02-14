"""modules/integration/field_mapping.py — Field mapping from insurer fields to AARS fields."""
from __future__ import annotations


# Default field mappings per source system.
# Keys = common insurer field names, values = AARS field names.
_DEFAULT_MAPPINGS: dict[str, dict[str, str]] = {
    "pas": {
        "agent_id": "agent_code",
        "agent_no": "agent_code",
        "advisor_code": "agent_code",
        "name": "full_name",
        "agent_name": "full_name",
        "mobile": "phone",
        "mobile_no": "phone",
        "phone_number": "phone",
        "email_id": "email",
        "email_address": "email",
        "policy_no": "policy_number",
        "pol_number": "policy_number",
        "product": "product_name",
        "premium": "premium_amount",
        "sum_assured": "sum_assured",
        "policy_start_date": "policy_date",
        "issue_date": "policy_date",
        "licence_no": "license_number",
        "license_no": "license_number",
        "language": "preferred_language",
        "lang": "preferred_language",
        "state": "lifecycle_state",
        "adm_code": "assigned_adm_id",
        "adm_assignment": "assigned_adm_id",
        "reporting_adm": "assigned_adm_id",
        "region": "region_node_id",
        "branch": "region_node_id",
        "area": "region_node_id",
        "license_expiry": "license_expiry_date",
        "licence_expiry": "license_expiry_date",
        "license_valid_till": "license_expiry_date",
        "onboarding_date": "onboarding_date",
        "joining_date": "onboarding_date",
        "doj": "onboarding_date",
        "date_of_joining": "onboarding_date",
    },
    "lms": {
        "agent_id": "agent_code",
        "agent_no": "agent_code",
        "advisor_code": "agent_code",
        "course_name": "training_name",
        "module_name": "training_name",
        "training_module": "training_name",
        "completed_on": "completion_date",
        "date_completed": "completion_date",
        "completion_dt": "completion_date",
        "marks": "score",
        "percentage": "score",
        "result": "status",
        "duration_hours": "hours",
        "training_hours": "hours",
        "licence_no": "license_number",
        "license_no": "license_number",
        "licence_status": "status",
        "license_status": "status",
        "expiry_dt": "expiry_date",
        "expiry_date": "expiry_date",
        "valid_till": "expiry_date",
        "training_hours": "training_hours_completed",
        "hours_completed": "training_hours_completed",
    },
    "commission": {
        "agent_id": "agent_code",
        "agent_no": "agent_code",
        "advisor_code": "agent_code",
        "commission_amount": "amount",
        "comm_amt": "amount",
        "payout": "amount",
        "credit_dt": "credit_date",
        "payment_date": "credit_date",
        "payout_date": "credit_date",
        "policy_no": "policy_number",
        "pol_number": "policy_number",
        "type": "commission_type",
        "comm_type": "commission_type",
    },
}


def get_default_mapping(source_system: str) -> dict[str, str]:
    """Return sensible default field mapping for a source system."""
    return _DEFAULT_MAPPINGS.get(source_system, {})


def apply_field_mapping(row: dict, mapping: dict[str, str]) -> dict:
    """Transform insurer field names to AARS field names using the mapping.

    Fields not in the mapping are passed through with their original key
    (lowercased and stripped).
    """
    result = {}
    for key, value in row.items():
        normalized_key = key.strip().lower().replace(" ", "_")
        mapped_key = mapping.get(normalized_key, normalized_key)
        result[mapped_key] = value.strip() if isinstance(value, str) else value
    return result
