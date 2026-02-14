"""modules/adm/schemas.py — ADM Experience Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ─── Morning Briefing ─────────────────────────────────────────────────────────

class BriefingSnapshot(BaseModel):
    active_count: int = 0
    at_risk_count: int = 0
    at_risk_change: int = 0  # +/- vs 7 days ago
    dormant_count: int = 0


class BriefingPriority(BaseModel):
    agent_id: uuid.UUID
    agent_name: str
    one_line_context: str
    suggested_action: str
    priority_emoji: str = "🔵"  # 🔴 urgent, 🟡 opportunity, 🟢 positive, 🔵 default


class BriefingCelebration(BaseModel):
    agent_id: uuid.UUID
    agent_name: str
    achievement: str


class MorningBriefingResponse(BaseModel):
    id: uuid.UUID
    adm_id: uuid.UUID
    briefing_date: date
    snapshot: BriefingSnapshot
    priorities: list[BriefingPriority]
    celebrations: list[BriefingCelebration]
    delivered_at: datetime | None = None
    read_at: datetime | None = None

    model_config = {"from_attributes": True}


# ─── Agent Detail ─────────────────────────────────────────────────────────────

class RecentSignalSummary(BaseModel):
    date: str
    channel: str
    summary: str


class QuickAction(BaseModel):
    id: str
    label: str


class AgentDetailResponse(BaseModel):
    agent_id: uuid.UUID
    agent_name: str
    lifecycle_state: str
    days_in_state: int
    last_contact_date: str | None = None
    last_contact_channel: str | None = None
    recent_signals: list[RecentSignalSummary]
    system_recommendation: str
    quick_actions: list[QuickAction]


# ─── ADM Action ───────────────────────────────────────────────────────────────

class ADMActionCreate(BaseModel):
    agent_id: uuid.UUID
    action_type: str  # CALLED_AGENT, VISITED_AGENT, SENT_TRAINING, ESCALATED, ACKNOWLEDGED, FORWARDED_CONTENT
    notes: str | None = None
    outcome: dict | None = None  # {result: "positive"|"okay"|"not_great"|"skip"}
    source: str = "MANUAL"


class ADMActionResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    adm_id: uuid.UUID
    agent_id: uuid.UUID
    action_type: str
    notes: str | None = None
    outcome: dict | None = None
    source: str
    nudge_reference_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Alerts ───────────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    adm_id: uuid.UUID
    agent_id: uuid.UUID
    alert_type: str
    urgency: str
    message: str
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    acted_on_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Weekly Summary ───────────────────────────────────────────────────────────

class WeeklyWin(BaseModel):
    agent_name: str
    achievement: str


class WeeklyMovement(BaseModel):
    newly_active_count: int = 0
    newly_at_risk_count: int = 0
    reengaged_count: int = 0


class ADMNumbers(BaseModel):
    agents_contacted: int = 0
    system_assisted_contacts: int = 0
    training_completions: int = 0


class WeeklySummaryResponse(BaseModel):
    id: uuid.UUID
    adm_id: uuid.UUID
    week_start: date
    week_end: date
    wins: list[WeeklyWin]
    movement: WeeklyMovement
    adm_numbers: ADMNumbers
    focus_areas: list[str]
    delivered_at: datetime | None = None
    read_at: datetime | None = None

    model_config = {"from_attributes": True}


# ─── ADM Effectiveness ───────────────────────────────────────────────────────

class PortfolioStats(BaseModel):
    total_agents: int = 0
    agents_by_state: dict[str, int] = Field(default_factory=dict)
    activation_rate: float = 0.0


class EngagementStats(BaseModel):
    agents_contacted_last_30d: int = 0
    nudges_received: int = 0
    nudges_acted_on: int = 0
    nudge_response_rate: float = 0.0
    average_time_to_act_hours: float = 0.0


class EffectivenessStats(BaseModel):
    reactivations_last_90d: int = 0
    first_sales_facilitated_last_90d: int = 0


class ADMEffectivenessResponse(BaseModel):
    adm_id: uuid.UUID
    portfolio: PortfolioStats
    engagement: EngagementStats
    effectiveness: EffectivenessStats
    classification: str  # HIGH_PERFORMER, AVERAGE, STRUGGLING, UNRESPONSIVE
    classification_reason: str
