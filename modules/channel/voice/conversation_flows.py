"""modules/channel/voice/conversation_flows.py — Structured conversation flow guides.

These flows are REFERENCE configurations for Vibrium's dashboard bot setup.
They define the purpose, opening script, branches, and signal extraction
requirements for each conversation type. Our code uses them to:
1. Generate the conversation_guide field in VoiceCallRequest
2. Validate expected signal types from webhooks
3. Document the intended conversation design
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationFlow:
    flow_id: str
    name: str
    purpose: str
    max_duration_seconds: int
    opening_template: str
    signal_types: list[str]
    context_fields: list[str] = field(default_factory=list)


FIRST_CONTACT = ConversationFlow(
    flow_id="first_contact",
    name="First-Contact Call",
    purpose="Welcome newly onboarded agent, set expectations, assess readiness",
    max_duration_seconds=300,
    opening_template=(
        "Namaste {agent_name} ji, main {persona_name} bol rahi hoon "
        "{company_name} se. Aapne recently {company_name} ke saath associate "
        "kiya hai, toh main aapka swagat karne ke liye call kar rahi hoon. "
        "Kya aap 2-3 minute baat kar sakte hain?"
    ),
    signal_types=[
        "voice_call_initiated",
        "voice_call_outcome",
        "voice_conversation_analyzed",
    ],
    context_fields=["agent_name", "persona_name", "company_name", "adm_name"],
)

DORMANT_CHECK_IN = ConversationFlow(
    flow_id="dormant_check_in",
    name="Dormant Agent Check-In",
    purpose="Understand why agent stopped, classify dormancy reason, explore reactivation",
    max_duration_seconds=480,
    opening_template=(
        "Namaste {agent_name} ji, main {persona_name}, {company_name} se. "
        "Humein laga ki kaafi samay ho gaya aapse baat kiye, toh socha check "
        "kar lein ki sab theek hai. Kya 2-3 minute baat ho sakti hai?"
    ),
    signal_types=[
        "voice_call_initiated",
        "voice_call_outcome",
        "voice_conversation_analyzed",
    ],
    context_fields=[
        "agent_name", "persona_name", "company_name", "adm_name",
        "months_since_last_sale", "last_interaction_date",
    ],
)

CONGRATULATION = ConversationFlow(
    flow_id="congratulation",
    name="Congratulations Call",
    purpose="Celebrate agent's sale, reinforce positive behavior, identify next opportunity",
    max_duration_seconds=180,
    opening_template=(
        "{agent_name} ji, badhai ho! Aapki {product_name} policy issue ho gayi hai! "
        "Main {persona_name}, {company_name} se, aapko congratulate karne ke liye "
        "call kar rahi hoon."
    ),
    signal_types=[
        "voice_call_initiated",
        "voice_call_outcome",
        "voice_conversation_analyzed",
    ],
    context_fields=[
        "agent_name", "persona_name", "company_name", "product_name",
        "adm_name", "is_first_sale",
    ],
)

LICENSE_RENEWAL = ConversationFlow(
    flow_id="license_renewal",
    name="License Expiry Reminder",
    purpose="Alert agent about expiring license, help complete renewal requirements",
    max_duration_seconds=300,
    opening_template=(
        "{agent_name} ji, main {persona_name}, {company_name} se. Ek important "
        "information deni thi — aapka IRDAI license {expiry_date} ko expire ho "
        "raha hai. Renewal ke liye kuch steps complete karne hain."
    ),
    signal_types=[
        "voice_call_initiated",
        "voice_call_outcome",
        "voice_conversation_analyzed",
    ],
    context_fields=[
        "agent_name", "persona_name", "company_name",
        "expiry_date", "remaining_hours", "completed_hours",
    ],
)

# Registry of all flows
FLOWS: dict[str, ConversationFlow] = {
    "first_contact": FIRST_CONTACT,
    "dormant_check_in": DORMANT_CHECK_IN,
    "congratulation": CONGRATULATION,
    "license_renewal": LICENSE_RENEWAL,
}


def get_flow(flow_id: str) -> ConversationFlow | None:
    """Look up a conversation flow by ID."""
    return FLOWS.get(flow_id)


def render_opening(flow: ConversationFlow, context: dict) -> str:
    """Render the opening template with context values."""
    try:
        return flow.opening_template.format(**context)
    except KeyError:
        return flow.opening_template
