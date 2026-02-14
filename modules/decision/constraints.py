"""modules/decision/constraints.py — 5 hard constraints that NEVER get overridden.

CONSTRAINT_001: Consent — block if consent denied/revoked for chosen channel
CONSTRAINT_002: Opt-out (DND) — block voice if DND registered & not confirmed
CONSTRAINT_003: TRAI hours — voice calls only 09:00-21:00 IST
CONSTRAINT_004: Frequency cap — max contacts per month
CONSTRAINT_005: Terminal state — LAPSED/TERMINATED → DO_NOTHING
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from modules.decision.schemas import DecisionInput


@dataclass
class ConstraintResult:
    """Result of a constraint check."""
    allowed: bool
    reason: str
    defer_to: datetime | None = None


def check_consent(inp: DecisionInput, channel: str | None) -> ConstraintResult:
    """CONSTRAINT_001: Block if consent for chosen channel is denied/revoked."""
    if channel is None:
        return ConstraintResult(allowed=True, reason="No channel specified")

    channel_consent_map = {
        "voice_ai": "voice",
        "adm_call": "voice",
        "whatsapp_bot": "whatsapp",
        "whatsapp_adm": "whatsapp",
    }
    consent_key = channel_consent_map.get(channel)
    if consent_key is None:
        return ConstraintResult(allowed=True, reason=f"No consent required for {channel}")

    status = inp.consent.get(consent_key, "not_asked")
    if status in ("denied", "revoked"):
        return ConstraintResult(
            allowed=False,
            reason=f"Consent for {consent_key} is {status}",
        )
    return ConstraintResult(allowed=True, reason="Consent OK")


def check_opt_out(inp: DecisionInput, channel: str | None) -> ConstraintResult:
    """CONSTRAINT_002: DND-registered agents cannot receive voice calls unless confirmed."""
    if channel not in ("voice_ai", "adm_call"):
        return ConstraintResult(allowed=True, reason="Not a voice channel")

    if inp.dnd_registered and not inp.dnd_call_classification_confirmed:
        return ConstraintResult(
            allowed=False,
            reason="Agent is DND-registered; call classification not confirmed",
        )
    return ConstraintResult(allowed=True, reason="DND OK")


def check_trai_hours(
    inp: DecisionInput, channel: str | None, scheduled_time: datetime,
) -> ConstraintResult:
    """CONSTRAINT_003: Voice calls only between 09:00-21:00 IST.

    TRAI hours apply ONLY to voice calls, NOT to WhatsApp.
    """
    if channel not in ("voice_ai", "adm_call"):
        return ConstraintResult(allowed=True, reason="TRAI hours apply only to voice")

    # Convert to IST (UTC+5:30)
    ist_offset = timedelta(hours=5, minutes=30)
    ist_time = scheduled_time + ist_offset
    hour = ist_time.hour

    if hour < 9 or hour >= 21:
        # Defer to next 09:00 IST
        next_day = ist_time.date()
        if hour >= 21:
            next_day += timedelta(days=1)
        defer_ist = datetime(next_day.year, next_day.month, next_day.day, 9, 0, 0)
        defer_utc = (defer_ist - ist_offset).replace(tzinfo=timezone.utc)
        return ConstraintResult(
            allowed=False,
            reason="Outside TRAI calling hours (09:00-21:00 IST)",
            defer_to=defer_utc,
        )
    return ConstraintResult(allowed=True, reason="Within TRAI hours")


def check_frequency_cap(
    inp: DecisionInput, max_contacts_per_month: int = 10,
) -> ConstraintResult:
    """CONSTRAINT_004: Max contacts per month to avoid harassment."""
    if inp.contacts_this_month >= max_contacts_per_month:
        return ConstraintResult(
            allowed=False,
            reason=f"Frequency cap reached: {inp.contacts_this_month}/{max_contacts_per_month} contacts this month",
        )
    return ConstraintResult(allowed=True, reason="Within frequency cap")


def check_terminal_state(inp: DecisionInput) -> ConstraintResult:
    """CONSTRAINT_005: LAPSED or TERMINATED agents get DO_NOTHING."""
    if inp.lifecycle_state in ("lapsed", "terminated"):
        return ConstraintResult(
            allowed=False,
            reason=f"Agent in terminal state: {inp.lifecycle_state}",
        )
    return ConstraintResult(allowed=True, reason="Not in terminal state")


def run_all_constraints(
    inp: DecisionInput,
    channel: str | None,
    scheduled_time: datetime,
) -> ConstraintResult:
    """Run all 5 constraints in order. Returns first failure, or success."""
    for check in (
        lambda: check_terminal_state(inp),
        lambda: check_consent(inp, channel),
        lambda: check_opt_out(inp, channel),
        lambda: check_trai_hours(inp, channel, scheduled_time),
        lambda: check_frequency_cap(inp),
    ):
        result = check()
        if not result.allowed:
            return result

    return ConstraintResult(allowed=True, reason="All constraints passed")
