"""seeds/default_playbooks.py — Default playbook definitions per spec section 2.8.

Six playbooks that are seeded as is_default=True for every tenant:
1. Training Gap — Product Knowledge
2. Engagement Gap — ADM Never Contacted
3. Economic — Commission Concerns
4. License Renewal Urgent
5. First Sale Celebration
6. Dormant Re-engagement (generic)
"""
from __future__ import annotations

from core.enums import PlaybookActionType


def get_default_playbooks() -> list[dict]:
    """Return playbook definitions with their steps.

    Each dict has keys: name, description, trigger_conditions, success_criteria,
    max_duration_days, steps (list of step dicts).
    """
    return [
        # ── 1. Training Gap — Product Knowledge ──────────────────────
        {
            "name": "Training Gap — Product Knowledge",
            "description": (
                "For agents with dormancy reason in training_gap category. "
                "Sends product training content, quiz, and routes to ADM for guided sale."
            ),
            "trigger_conditions": {
                "lifecycle_state": "dormant",
                "dormancy_reason_category": "training_gap",
            },
            "success_criteria": {
                "target_state": "licensed",
                "or": {"signal_type": "policy_sold"},
            },
            "max_duration_days": 30,
            "steps": [
                {
                    "step_number": 1,
                    "name": "Ask product interest",
                    "action_type": PlaybookActionType.WHATSAPP_MESSAGE,
                    "action_config": {
                        "template": "product_interest_query",
                        "message": (
                            "Namaste! We noticed you might need help with product knowledge. "
                            "Which product would you like to learn about? "
                            "Reply: 1) Term Life 2) Endowment 3) ULIP 4) Health"
                        ),
                    },
                    "delay_days": 0,
                    "next_step_rules": [],
                },
                {
                    "step_number": 2,
                    "name": "Send product micro-training video",
                    "action_type": PlaybookActionType.WHATSAPP_TRAINING,
                    "action_config": {
                        "training_topic": "based_on_reply",
                        "fallback_topic": "product_term_life",
                        "content_type": "video",
                        "message": "Here's a short training video. Watch it and then take the quiz!",
                    },
                    "delay_days": 1,
                    "next_step_rules": [],
                },
                {
                    "step_number": 3,
                    "name": "Quiz (3-5 questions)",
                    "action_type": PlaybookActionType.WHATSAPP_TRAINING,
                    "action_config": {
                        "content_type": "quiz",
                        "quiz_questions": 5,
                        "pass_score": 60,
                    },
                    "delay_days": 1,
                    "next_step_rules": [
                        {
                            "condition": {"field": "quiz_score", "op": ">=", "value": 60},
                            "go_to_step": 4,
                        },
                        {
                            "condition": {"field": "quiz_score", "op": "<", "value": 60},
                            "go_to_step": 2,
                        },
                    ],
                },
                {
                    "step_number": 4,
                    "name": "ADM nudge — agent ready for guided sale",
                    "action_type": PlaybookActionType.ADM_NUDGE,
                    "action_config": {
                        "nudge_type": "GUIDED_SALE_READY",
                        "message": (
                            "{agent_name} completed product training with score {quiz_score}%. "
                            "They're ready for a guided first sale. Please schedule a joint call."
                        ),
                    },
                    "delay_days": 0,
                    "next_step_rules": [],
                },
                {
                    "step_number": 5,
                    "name": "Voice AI follow-up if ADM doesn't act",
                    "action_type": PlaybookActionType.VOICE_CALL,
                    "action_config": {
                        "purpose": "training",
                        "fallback_for": "adm_nudge",
                        "wait_for_adm_days": 3,
                        "conversation_guide": "training_followup",
                    },
                    "delay_days": 3,
                    "next_step_rules": [],
                },
            ],
        },
        # ── 2. Engagement Gap — ADM Never Contacted ──────────────────
        {
            "name": "Engagement Gap — ADM Never Contacted",
            "description": (
                "For agents whose ADM has never made contact. "
                "Nudges ADM, falls back to Voice AI if ADM doesn't act."
            ),
            "trigger_conditions": {
                "lifecycle_state": "dormant",
                "dormancy_reason": "engagement_gap.adm_never_contacted",
            },
            "success_criteria": {
                "signal_type": "adm_agent_call_logged",
            },
            "max_duration_days": 14,
            "steps": [
                {
                    "step_number": 1,
                    "name": "ADM nudge — new agent needs contact",
                    "action_type": PlaybookActionType.ADM_NUDGE,
                    "action_config": {
                        "nudge_type": "FIRST_CONTACT_NEEDED",
                        "urgency": "HIGH",
                        "message": (
                            "{agent_name} was onboarded but has never been contacted. "
                            "Please reach out today — first contact is critical for retention."
                        ),
                    },
                    "delay_days": 0,
                    "next_step_rules": [],
                },
                {
                    "step_number": 2,
                    "name": "Wait for ADM action",
                    "action_type": PlaybookActionType.WAIT,
                    "action_config": {"wait_days": 3},
                    "delay_days": 3,
                    "next_step_rules": [
                        {
                            "condition": {"field": "adm_acted", "op": "==", "value": True},
                            "go_to_step": 4,
                        },
                    ],
                },
                {
                    "step_number": 3,
                    "name": "Voice AI first contact call",
                    "action_type": PlaybookActionType.VOICE_CALL,
                    "action_config": {
                        "purpose": "first_contact",
                        "conversation_guide": "first_contact_check_in",
                    },
                    "delay_days": 0,
                    "next_step_rules": [],
                },
                {
                    "step_number": 4,
                    "name": "WhatsApp training content",
                    "action_type": PlaybookActionType.WHATSAPP_TRAINING,
                    "action_config": {
                        "training_topic": "sales_pitch",
                        "message": "Here's some training material to help you get started!",
                    },
                    "delay_days": 1,
                    "next_step_rules": [],
                },
            ],
        },
        # ── 3. Economic — Commission Concerns ────────────────────────
        {
            "name": "Economic — Commission Concerns",
            "description": (
                "For agents with economic dormancy reasons (commission too low, "
                "competitor better commission, irregular payments)."
            ),
            "trigger_conditions": {
                "lifecycle_state": "dormant",
                "dormancy_reason_category": "economic",
            },
            "success_criteria": {
                "signal_type": "policy_sold",
            },
            "max_duration_days": 21,
            "steps": [
                {
                    "step_number": 1,
                    "name": "WhatsApp commission structure explainer",
                    "action_type": PlaybookActionType.WHATSAPP_MESSAGE,
                    "action_config": {
                        "template": "commission_explainer",
                        "message": (
                            "We understand commission matters. Here's a clear breakdown of "
                            "our commission structure and how top agents earn 2-3x more. "
                            "Check out these earning scenarios."
                        ),
                    },
                    "delay_days": 0,
                    "next_step_rules": [],
                },
                {
                    "step_number": 2,
                    "name": "Voice AI call to understand specific concern",
                    "action_type": PlaybookActionType.VOICE_CALL,
                    "action_config": {
                        "purpose": "reactivation",
                        "conversation_guide": "commission_concern",
                    },
                    "delay_days": 2,
                    "next_step_rules": [],
                },
                {
                    "step_number": 3,
                    "name": "ADM nudge with agent's concerns",
                    "action_type": PlaybookActionType.ADM_NUDGE,
                    "action_config": {
                        "nudge_type": "COMMISSION_CONCERN",
                        "message": (
                            "{agent_name} has commission concerns: {concern_details}. "
                            "Please discuss earning potential and address their specific issues."
                        ),
                    },
                    "delay_days": 1,
                    "next_step_rules": [],
                },
            ],
        },
        # ── 4. License Renewal Urgent ─────────────────────────────────
        {
            "name": "License Renewal Urgent",
            "description": (
                "For agents whose license is expiring within 60 days. "
                "Escalating reminders until renewal or escalation."
            ),
            "trigger_conditions": {
                "license_expiry_days_remaining": {"op": "<=", "value": 60},
            },
            "success_criteria": {
                "signal_type": "license_status_changed",
                "payload.new_status": "ACTIVE",
            },
            "max_duration_days": 45,
            "steps": [
                {
                    "step_number": 1,
                    "name": "WhatsApp license expiry reminder with training link",
                    "action_type": PlaybookActionType.WHATSAPP_MESSAGE,
                    "action_config": {
                        "template": "license_renewal_reminder",
                        "message": (
                            "Your IRDAI license expires in {days_remaining} days. "
                            "Complete your training hours to renew. Tap here for training modules."
                        ),
                    },
                    "delay_days": 0,
                    "next_step_rules": [],
                },
                {
                    "step_number": 2,
                    "name": "Daily WhatsApp reminders",
                    "action_type": PlaybookActionType.WHATSAPP_MESSAGE,
                    "action_config": {
                        "template": "license_daily_reminder",
                        "repeat": True,
                        "repeat_interval_days": 1,
                        "max_repeats": 7,
                        "message": "Reminder: Your license renewal is pending. Complete training to renew.",
                    },
                    "delay_days": 1,
                    "next_step_rules": [],
                },
                {
                    "step_number": 3,
                    "name": "ADM nudge if no progress in 7 days",
                    "action_type": PlaybookActionType.ADM_NUDGE,
                    "action_config": {
                        "nudge_type": "LICENSE_RENEWAL_AT_RISK",
                        "urgency": "HIGH",
                        "message": (
                            "{agent_name}'s license expires in {days_remaining} days "
                            "with no renewal progress. Please contact them urgently."
                        ),
                    },
                    "delay_days": 7,
                    "next_step_rules": [],
                },
                {
                    "step_number": 4,
                    "name": "Escalate to Regional Manager if 30 days left",
                    "action_type": PlaybookActionType.ESCALATE,
                    "action_config": {
                        "escalate_to": "regional_manager",
                        "urgency": "CRITICAL",
                        "message": (
                            "URGENT: {agent_name}'s license expires in {days_remaining} days. "
                            "ADM has been notified but no action taken. Requires immediate intervention."
                        ),
                    },
                    "delay_days": 7,
                    "next_step_rules": [],
                },
            ],
        },
        # ── 5. First Sale Celebration ─────────────────────────────────
        {
            "name": "First Sale Celebration",
            "description": (
                "Triggered when an agent makes their first policy sale. "
                "Celebrates the achievement to reinforce positive behavior."
            ),
            "trigger_conditions": {
                "lifecycle_state": "first_sale",
                "total_policies": 1,
            },
            "success_criteria": {
                "signal_type": "policy_sold",
                "min_count": 2,
            },
            "max_duration_days": 7,
            "steps": [
                {
                    "step_number": 1,
                    "name": "Voice AI congratulations call",
                    "action_type": PlaybookActionType.VOICE_CALL,
                    "action_config": {
                        "purpose": "congratulation",
                        "conversation_guide": "first_sale_celebration",
                        "persona_name": "Priya",
                    },
                    "delay_days": 0,
                    "next_step_rules": [],
                },
                {
                    "step_number": 2,
                    "name": "WhatsApp celebration message",
                    "action_type": PlaybookActionType.WHATSAPP_MESSAGE,
                    "action_config": {
                        "template": "first_sale_celebration",
                        "message": (
                            "Congratulations on your FIRST sale! "
                            "You're now officially on the path to success. "
                            "Here are tips for your second sale."
                        ),
                    },
                    "delay_days": 0,
                    "next_step_rules": [],
                },
                {
                    "step_number": 3,
                    "name": "ADM nudge to reinforce",
                    "action_type": PlaybookActionType.ADM_NUDGE,
                    "action_config": {
                        "nudge_type": "FIRST_SALE_CELEBRATION",
                        "message": (
                            "{agent_name} just made their FIRST sale! "
                            "Please congratulate them and help maintain momentum."
                        ),
                    },
                    "delay_days": 0,
                    "next_step_rules": [],
                },
            ],
        },
        # ── 6. Dormant Re-engagement (Generic) ───────────────────────
        {
            "name": "Dormant Re-engagement — Generic",
            "description": (
                "Generic re-engagement playbook for dormant agents whose "
                "specific reason is unknown or doesn't match other playbooks. "
                "Uses Voice AI to identify the reason and routes to specific playbook."
            ),
            "trigger_conditions": {
                "lifecycle_state": "dormant",
            },
            "success_criteria": {
                "dormancy_reason_identified": True,
                "or": {"signal_type": "policy_sold"},
            },
            "max_duration_days": 21,
            "steps": [
                {
                    "step_number": 1,
                    "name": "WhatsApp gentle check-in",
                    "action_type": PlaybookActionType.WHATSAPP_MESSAGE,
                    "action_config": {
                        "template": "dormant_check_in",
                        "message": (
                            "Hi {agent_name}, it's been a while! "
                            "We'd love to help you get back on track. "
                            "Is there anything we can help with?"
                        ),
                    },
                    "delay_days": 0,
                    "next_step_rules": [],
                },
                {
                    "step_number": 2,
                    "name": "Wait for response",
                    "action_type": PlaybookActionType.WAIT,
                    "action_config": {"wait_days": 3},
                    "delay_days": 3,
                    "next_step_rules": [],
                },
                {
                    "step_number": 3,
                    "name": "Voice AI check-in call",
                    "action_type": PlaybookActionType.VOICE_CALL,
                    "action_config": {
                        "purpose": "reactivation",
                        "conversation_guide": "dormant_check_in",
                        "extract": ["dormancy_reason", "product_interest", "sentiment"],
                    },
                    "delay_days": 0,
                    "next_step_rules": [
                        {
                            "condition": {
                                "field": "dormancy_reason_category",
                                "op": "==",
                                "value": "training_gap",
                            },
                            "action": "route_to_playbook",
                            "playbook": "Training Gap — Product Knowledge",
                        },
                        {
                            "condition": {
                                "field": "dormancy_reason_category",
                                "op": "==",
                                "value": "economic",
                            },
                            "action": "route_to_playbook",
                            "playbook": "Economic — Commission Concerns",
                        },
                    ],
                },
                {
                    "step_number": 4,
                    "name": "ADM nudge with extracted reason",
                    "action_type": PlaybookActionType.ADM_NUDGE,
                    "action_config": {
                        "nudge_type": "DORMANCY_REASON_IDENTIFIED",
                        "message": (
                            "{agent_name}'s dormancy reason: {dormancy_reason}. "
                            "Recommended action: {suggested_action}."
                        ),
                    },
                    "delay_days": 1,
                    "next_step_rules": [],
                },
            ],
        },
    ]
