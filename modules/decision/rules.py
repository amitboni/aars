"""modules/decision/rules.py — 10+ decision rules evaluated in priority order.

Rules are grouped by urgency tier:
  URGENT  — immediate attention needed
  OPP     — time-sensitive opportunity
  PROACTIVE — scheduled engagement
  ADM_COMP — ADM competence compensation

First match wins. If no rule matches → DO_NOTHING.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.enums import DecisionAction
from modules.decision.schemas import DecisionInput, DecisionOutput


@dataclass
class RuleMatch:
    matched: bool
    output: DecisionOutput | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_since(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    return (_now() - dt).days


# ── URGENT Rules ────────────────────────────────────────────────────────

def rule_urgent_001(inp: DecisionInput) -> RuleMatch:
    """License expiry < 60 days AND training hours remaining > 10 → START_PLAYBOOK."""
    if inp.license_expiry_date is None:
        return RuleMatch(matched=False)

    days_to_expiry = (inp.license_expiry_date - _now()).days
    if days_to_expiry < 60 and inp.training_hours_remaining > 10:
        return RuleMatch(
            matched=True,
            output=DecisionOutput(
                action=DecisionAction.START_PLAYBOOK,
                rule_id="URGENT_001",
                scheduled_time=_now(),
                channel="whatsapp_bot",
                priority="URGENT",
                reasoning=(
                    f"License expires in {days_to_expiry} days with "
                    f"{inp.training_hours_remaining:.0f}h training remaining"
                ),
            ),
        )
    return RuleMatch(matched=False)


def rule_urgent_002(inp: DecisionInput) -> RuleMatch:
    """AT_RISK agent who was recently PRODUCTIVE (< 14 days) → SEND_NUDGE_TO_ADM."""
    if (
        inp.lifecycle_state == "at_risk"
        and inp.previous_state == "productive"
        and inp.days_in_state < 14
    ):
        return RuleMatch(
            matched=True,
            output=DecisionOutput(
                action=DecisionAction.SEND_NUDGE_TO_ADM,
                rule_id="URGENT_002",
                scheduled_time=_now(),
                channel="whatsapp_adm",
                priority="HIGH",
                reasoning=(
                    f"Recently productive agent now at risk "
                    f"({inp.days_in_state} days). ADM intervention needed."
                ),
            ),
        )
    return RuleMatch(matched=False)


# ── OPPORTUNITY Rules ──────────────────────────────────────────────────

def rule_opp_001(inp: DecisionInput) -> RuleMatch:
    """Dormant agent with recent positive signal (≤7 days) → SEND_NUDGE_TO_ADM."""
    if inp.lifecycle_state != "dormant":
        return RuleMatch(matched=False)

    days = _days_since(inp.last_positive_signal_at)
    if days is not None and days <= 7:
        return RuleMatch(
            matched=True,
            output=DecisionOutput(
                action=DecisionAction.SEND_NUDGE_TO_ADM,
                rule_id="OPP_001",
                scheduled_time=_now(),
                channel="whatsapp_adm",
                priority="HIGH",
                reasoning=(
                    f"Dormant agent showed positive signal {days} days ago. "
                    f"Reactivation window open."
                ),
            ),
        )
    return RuleMatch(matched=False)


def rule_opp_002(inp: DecisionInput) -> RuleMatch:
    """Newly onboarded agent with no contact after 3 days → SCHEDULE_VOICE_CALL."""
    if inp.lifecycle_state != "onboarded":
        return RuleMatch(matched=False)

    if inp.days_in_state > 3 and inp.last_contact_at is None:
        return RuleMatch(
            matched=True,
            output=DecisionOutput(
                action=DecisionAction.SCHEDULE_VOICE_CALL,
                rule_id="OPP_002",
                scheduled_time=_now(),
                channel="voice_ai",
                priority="MEDIUM",
                reasoning=(
                    f"Onboarded agent with no contact after "
                    f"{inp.days_in_state} days. First contact overdue."
                ),
            ),
        )
    return RuleMatch(matched=False)


def rule_opp_003(inp: DecisionInput) -> RuleMatch:
    """First policy sold (total==1, sold within 3 days) → CELEBRATE."""
    if inp.total_policies == 1 and inp.last_sale_date is not None:
        days = _days_since(inp.last_sale_date)
        if days is not None and days <= 3:
            return RuleMatch(
                matched=True,
                output=DecisionOutput(
                    action=DecisionAction.CELEBRATE,
                    rule_id="OPP_003",
                    scheduled_time=_now(),
                    channel="whatsapp_bot",
                    priority="MEDIUM",
                    reasoning="First policy sold! Celebrate to reinforce positive behavior.",
                ),
            )
    return RuleMatch(matched=False)


# ── PROACTIVE Rules ────────────────────────────────────────────────────

def rule_proactive_001(inp: DecisionInput) -> RuleMatch:
    """Licensed agent with < 3 training modules → SEND_TRAINING."""
    if inp.lifecycle_state == "licensed" and inp.training_modules_completed < 3:
        return RuleMatch(
            matched=True,
            output=DecisionOutput(
                action=DecisionAction.SEND_TRAINING,
                rule_id="PROACTIVE_001",
                scheduled_time=_now(),
                channel="whatsapp_bot",
                priority="MEDIUM",
                reasoning=(
                    f"Licensed agent with only {inp.training_modules_completed} "
                    f"training modules completed."
                ),
            ),
        )
    return RuleMatch(matched=False)


def rule_proactive_002(inp: DecisionInput) -> RuleMatch:
    """Active agent with no contact in 14+ days → SEND_WHATSAPP check-in."""
    if inp.lifecycle_state != "active":
        return RuleMatch(matched=False)

    days = _days_since(inp.last_contact_at)
    if days is not None and days >= 14:
        return RuleMatch(
            matched=True,
            output=DecisionOutput(
                action=DecisionAction.SEND_WHATSAPP,
                rule_id="PROACTIVE_002",
                scheduled_time=_now(),
                channel="whatsapp_bot",
                priority="LOW",
                reasoning=f"Active agent with no contact in {days} days. Check-in recommended.",
            ),
        )
    if inp.last_contact_at is None and inp.days_in_state >= 14:
        return RuleMatch(
            matched=True,
            output=DecisionOutput(
                action=DecisionAction.SEND_WHATSAPP,
                rule_id="PROACTIVE_002",
                scheduled_time=_now(),
                channel="whatsapp_bot",
                priority="LOW",
                reasoning="Active agent never contacted. Check-in recommended.",
            ),
        )
    return RuleMatch(matched=False)


def rule_proactive_003(inp: DecisionInput) -> RuleMatch:
    """Dormant agent with < 3 reactivation attempts → START_PLAYBOOK (reactivation)."""
    if inp.lifecycle_state == "dormant" and inp.reactivation_attempts < 3:
        return RuleMatch(
            matched=True,
            output=DecisionOutput(
                action=DecisionAction.START_PLAYBOOK,
                rule_id="PROACTIVE_003",
                scheduled_time=_now(),
                channel="whatsapp_bot",
                priority="MEDIUM",
                reasoning=(
                    f"Dormant agent with {inp.reactivation_attempts} reactivation "
                    f"attempts (max 3). Start reactivation playbook."
                ),
            ),
        )
    return RuleMatch(matched=False)


def rule_proactive_004(inp: DecisionInput) -> RuleMatch:
    """Productive agent with no contact in 30+ days → SEND_WHATSAPP maintenance."""
    if inp.lifecycle_state != "productive":
        return RuleMatch(matched=False)

    days = _days_since(inp.last_contact_at)
    if days is not None and days >= 30:
        return RuleMatch(
            matched=True,
            output=DecisionOutput(
                action=DecisionAction.SEND_WHATSAPP,
                rule_id="PROACTIVE_004",
                scheduled_time=_now(),
                channel="whatsapp_bot",
                priority="LOW",
                reasoning=f"Productive agent with no contact in {days} days. Maintenance check-in.",
            ),
        )
    return RuleMatch(matched=False)


# ── ADM COMPETENCE Rules ──────────────────────────────────────────────

def rule_adm_comp_001(inp: DecisionInput) -> RuleMatch:
    """Unresponsive ADM → engage agent directly + ESCALATE."""
    if inp.adm_classification == "UNRESPONSIVE":
        return RuleMatch(
            matched=True,
            output=DecisionOutput(
                action=DecisionAction.ESCALATE,
                rule_id="ADM_COMP_001",
                scheduled_time=_now(),
                channel="whatsapp_bot",
                priority="HIGH",
                reasoning="ADM classified as UNRESPONSIVE. Engaging agent directly and escalating.",
            ),
        )
    return RuleMatch(matched=False)


# ── Rule Chain ─────────────────────────────────────────────────────────

RULE_CHAIN: list = [
    rule_urgent_001,
    rule_urgent_002,
    rule_opp_001,
    rule_opp_002,
    rule_opp_003,
    rule_proactive_001,
    rule_proactive_002,
    rule_proactive_003,
    rule_proactive_004,
    rule_adm_comp_001,
]


def evaluate_rules(inp: DecisionInput) -> DecisionOutput:
    """Evaluate all rules in priority order. First match wins.

    Returns DO_NOTHING if no rule matches.
    """
    for rule_fn in RULE_CHAIN:
        result = rule_fn(inp)
        if result.matched and result.output is not None:
            return result.output

    return DecisionOutput(
        action=DecisionAction.DO_NOTHING,
        rule_id="DEFAULT",
        scheduled_time=_now(),
        priority="LOW",
        reasoning="No decision rule matched. No action needed.",
    )
