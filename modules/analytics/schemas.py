"""modules/analytics/schemas.py — Analytics Pydantic response schemas.

Per spec sections 3.7.1 and 3.7.2: dashboard, dormancy, reactivation funnel,
ADM performance, training effectiveness, and system ROI.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ─── Dashboard ───


class DashboardResponse(BaseModel):
    """Executive dashboard metrics (spec section 3.7.1)."""

    total_agents: int
    active_agents: int
    at_risk_agents: int
    dormant_agents: int
    agents_by_state: dict[str, int] = Field(
        description="Lifecycle state -> count"
    )
    agent_activation_rate: float = Field(
        description="(active + productive) / total non-terminated, as percentage"
    )
    agent_activation_trend: str = Field(
        description="up, down, or stable vs last month"
    )
    reactivation_count_this_month: int = Field(
        description="Agents who moved from DORMANT to ACTIVE/FIRST_SALE in last 30 days"
    )
    reactivation_by_intervention: dict[str, int] = Field(
        description="Channel that preceded reactivation -> count"
    )


# ─── Dormancy Analytics ───


class DormancyAnalyticsResponse(BaseModel):
    """Dormancy reason distribution and trends."""

    reason_distribution: dict[str, int] = Field(
        description="DormancyReasonCode -> count of dormant agents"
    )
    top_growing_reason: str | None = Field(
        description="Reason with largest increase vs last month"
    )
    top_shrinking_reason: str | None = Field(
        description="Reason with largest decrease vs last month"
    )
    trend_vs_last_month: dict[str, float] = Field(
        description="Reason -> percentage change vs last month"
    )
    regional_breakdown: dict[str, dict[str, int]] = Field(
        description="region_node_id -> reason -> count"
    )


# ─── Reactivation Funnel ───


class ReactivationFunnelResponse(BaseModel):
    """Reactivation pipeline: contacted -> engaged -> trained -> sold."""

    contacted: int
    engaged: int
    trained: int
    sold: int
    conversion_rates: dict[str, float] = Field(
        description="contacted_to_engaged, engaged_to_trained, trained_to_sold"
    )
    by_channel: dict[str, dict[str, int]] = Field(
        description="Channel -> {contacted, engaged, trained, sold}"
    )
    by_playbook: dict[str, dict[str, int]] = Field(
        description="Playbook name -> {contacted, engaged, trained, sold}"
    )


# ─── ADM Performance ───


class ADMRanking(BaseModel):
    adm_id: uuid.UUID
    name: str
    total_agents: int
    active_agents: int
    activation_rate: float
    nudge_response_rate: float
    reactivations_last_90d: int
    classification: str  # HIGH_PERFORMER, AVERAGE, STRUGGLING, UNRESPONSIVE


class ADMPerformanceResponse(BaseModel):
    """ADM performance rankings (spec section 3.7.2)."""

    adm_rankings: list[ADMRanking]
    top_5_adms: list[ADMRanking]
    bottom_5_adms: list[ADMRanking]
    average_activation_rate: float


# ─── Training Effectiveness ───


class TrainingEffectivenessResponse(BaseModel):
    """Training module effectiveness metrics."""

    completion_rate_by_module: dict[str, float] = Field(
        description="Module name -> completion rate"
    )
    average_scores_by_module: dict[str, float] = Field(
        description="Module name -> average quiz score"
    )
    training_to_sale_correlation: dict[str, float] = Field(
        description="Module name -> % who sold within 30 days of completing"
    )
    top_drop_off_modules: list[str] = Field(
        description="Modules with highest start-but-not-completed rate"
    )


# ─── System ROI ───


class SystemROIResponse(BaseModel):
    """System ROI calculation."""

    new_premium_from_reactivated: float = Field(
        description="Sum of premium from agents reactivated in period"
    )
    system_cost_this_month: float = Field(
        description="Estimated system cost for the period"
    )
    roi_multiplier: float = Field(
        description="premium / cost"
    )
    agents_reactivated: int
    average_premium_per_reactivation: float


# ─── Report Responses ───


class ReportResponse(BaseModel):
    """Generic report response."""

    report_type: str
    generated_at: datetime
    tenant_id: uuid.UUID
    period_start: date
    period_end: date
    data: dict
