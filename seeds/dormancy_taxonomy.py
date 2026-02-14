"""seeds/dormancy_taxonomy.py — Full dormancy reason taxonomy per spec section 2.5.

Each reason has: code, parent_category, name, description, detection_hints,
and suggested_intervention_playbook.
"""
from __future__ import annotations

from core.enums import DormancyReasonCategory, DormancyReasonCode


DORMANCY_TAXONOMY: list[dict] = [
    # ── TRAINING_GAP ─────────────────────────────────────────────────
    {
        "code": DormancyReasonCode.PRODUCT_KNOWLEDGE_INSUFFICIENT,
        "parent_category": DormancyReasonCategory.TRAINING_GAP,
        "name": "Product Knowledge Insufficient",
        "description": "Agent lacks knowledge about insurance products and cannot explain them to customers.",
        "detection_hints": [
            "product", "understand", "confused", "don't know", "what is",
            "term life", "endowment", "ulip", "explain", "features",
        ],
        "suggested_intervention_playbook": "training_gap_product_knowledge",
    },
    {
        "code": DormancyReasonCode.SALES_SKILLS_LACKING,
        "parent_category": DormancyReasonCategory.TRAINING_GAP,
        "name": "Sales Skills Lacking",
        "description": "Agent struggles with selling techniques — prospecting, pitching, objection handling, closing.",
        "detection_hints": [
            "sell", "pitch", "customer", "objection", "convince",
            "approach", "closing", "prospect", "rejection",
        ],
        "suggested_intervention_playbook": "training_gap_product_knowledge",
    },
    {
        "code": DormancyReasonCode.EXAM_NOT_ATTEMPTED,
        "parent_category": DormancyReasonCategory.TRAINING_GAP,
        "name": "Exam Not Attempted",
        "description": "Agent has not attempted the IRDAI/IC38 licensing exam yet.",
        "detection_hints": [
            "exam", "IC38", "IRDAI", "test", "license exam", "not attempted",
        ],
        "suggested_intervention_playbook": "training_gap_product_knowledge",
    },
    {
        "code": DormancyReasonCode.EXAM_FAILED,
        "parent_category": DormancyReasonCategory.TRAINING_GAP,
        "name": "Exam Failed",
        "description": "Agent failed the licensing exam and needs to prepare for retake.",
        "detection_hints": [
            "failed", "exam", "IC38", "not passed", "retake",
        ],
        "suggested_intervention_playbook": "training_gap_product_knowledge",
    },
    {
        "code": DormancyReasonCode.PROCESS_UNCLEAR,
        "parent_category": DormancyReasonCategory.TRAINING_GAP,
        "name": "Process Unclear",
        "description": "Agent doesn't understand operational processes (proposal, KYC, issuance).",
        "detection_hints": [
            "process", "form", "proposal", "KYC", "how to", "steps",
            "document", "submit", "procedure",
        ],
        "suggested_intervention_playbook": "training_gap_product_knowledge",
    },
    # ── ENGAGEMENT_GAP ───────────────────────────────────────────────
    {
        "code": DormancyReasonCode.ADM_NEVER_CONTACTED,
        "parent_category": DormancyReasonCategory.ENGAGEMENT_GAP,
        "name": "ADM Never Contacted",
        "description": "Agent was onboarded but their ADM has never reached out to them.",
        "detection_hints": [
            "no one called", "nobody contacted", "manager", "ADM",
            "never met", "no support", "alone",
        ],
        "suggested_intervention_playbook": "engagement_gap_adm_never_contacted",
    },
    {
        "code": DormancyReasonCode.ADM_NO_FOLLOWTHROUGH,
        "parent_category": DormancyReasonCategory.ENGAGEMENT_GAP,
        "name": "ADM No Follow-Through",
        "description": "ADM made initial contact but never followed up on commitments.",
        "detection_hints": [
            "promised", "follow up", "didn't call back", "no follow",
            "waiting", "said would help",
        ],
        "suggested_intervention_playbook": "engagement_gap_adm_never_contacted",
    },
    {
        "code": DormancyReasonCode.FEELS_UNSUPPORTED,
        "parent_category": DormancyReasonCategory.ENGAGEMENT_GAP,
        "name": "Feels Unsupported",
        "description": "Agent feels they don't have adequate support from the company or ADM.",
        "detection_hints": [
            "support", "help", "alone", "nobody", "unsupported",
            "on my own", "no guidance",
        ],
        "suggested_intervention_playbook": "engagement_gap_adm_never_contacted",
    },
    {
        "code": DormancyReasonCode.NO_RECOGNITION,
        "parent_category": DormancyReasonCategory.ENGAGEMENT_GAP,
        "name": "No Recognition",
        "description": "Agent feels their efforts and achievements are not recognized.",
        "detection_hints": [
            "recognition", "appreciate", "ignored", "no reward",
            "not valued", "incentive",
        ],
        "suggested_intervention_playbook": "engagement_gap_adm_never_contacted",
    },
    # ── ECONOMIC ─────────────────────────────────────────────────────
    {
        "code": DormancyReasonCode.COMMISSION_TOO_LOW,
        "parent_category": DormancyReasonCategory.ECONOMIC,
        "name": "Commission Too Low",
        "description": "Agent perceives commission rates as too low to be worthwhile.",
        "detection_hints": [
            "commission", "earning", "money", "income", "low pay",
            "not enough", "payout", "not worth",
        ],
        "suggested_intervention_playbook": "economic_commission_concerns",
    },
    {
        "code": DormancyReasonCode.COMPETITOR_BETTER_COMMISSION,
        "parent_category": DormancyReasonCategory.ECONOMIC,
        "name": "Competitor Better Commission",
        "description": "Agent knows of competitors offering better commission rates.",
        "detection_hints": [
            "other company", "competitor", "better rate", "LIC",
            "HDFC", "ICICI", "more commission",
        ],
        "suggested_intervention_playbook": "economic_commission_concerns",
    },
    {
        "code": DormancyReasonCode.IRREGULAR_PAYMENTS,
        "parent_category": DormancyReasonCategory.ECONOMIC,
        "name": "Irregular Payments",
        "description": "Agent experiences delays or irregularity in commission payments.",
        "detection_hints": [
            "payment", "delayed", "not received", "pending",
            "irregular", "late payment",
        ],
        "suggested_intervention_playbook": "economic_commission_concerns",
    },
    {
        "code": DormancyReasonCode.INSUFFICIENT_INCOME,
        "parent_category": DormancyReasonCategory.ECONOMIC,
        "name": "Insufficient Income",
        "description": "Agent cannot sustain themselves on insurance commission alone.",
        "detection_hints": [
            "full-time", "part-time", "other job", "not enough",
            "sustain", "livelihood", "income",
        ],
        "suggested_intervention_playbook": "economic_commission_concerns",
    },
    # ── OPERATIONAL ──────────────────────────────────────────────────
    {
        "code": DormancyReasonCode.PROPOSAL_PROCESS_COMPLEX,
        "parent_category": DormancyReasonCategory.OPERATIONAL,
        "name": "Proposal Process Complex",
        "description": "Agent finds the proposal/application process too complicated.",
        "detection_hints": [
            "proposal", "form", "complicated", "difficult", "complex",
            "too many", "paperwork",
        ],
        "suggested_intervention_playbook": "training_gap_product_knowledge",
    },
    {
        "code": DormancyReasonCode.TECHNOLOGY_BARRIERS,
        "parent_category": DormancyReasonCategory.OPERATIONAL,
        "name": "Technology Barriers",
        "description": "Agent struggles with digital tools and apps required for business.",
        "detection_hints": [
            "app", "technology", "digital", "phone", "internet",
            "computer", "login", "technical",
        ],
        "suggested_intervention_playbook": "training_gap_product_knowledge",
    },
    {
        "code": DormancyReasonCode.CLAIM_EXPERIENCE_BAD,
        "parent_category": DormancyReasonCategory.OPERATIONAL,
        "name": "Bad Claim Experience",
        "description": "Agent or their customers had bad claims experience, damaging trust.",
        "detection_hints": [
            "claim", "rejected", "denied", "customer angry",
            "bad experience", "trust",
        ],
        "suggested_intervention_playbook": "economic_commission_concerns",
    },
    {
        "code": DormancyReasonCode.SLOW_ISSUANCE,
        "parent_category": DormancyReasonCategory.OPERATIONAL,
        "name": "Slow Policy Issuance",
        "description": "Policies take too long to issue, frustrating agents and customers.",
        "detection_hints": [
            "issuance", "slow", "delay", "policy not issued",
            "pending", "waiting for policy",
        ],
        "suggested_intervention_playbook": "economic_commission_concerns",
    },
    {
        "code": DormancyReasonCode.KYC_ISSUES,
        "parent_category": DormancyReasonCategory.OPERATIONAL,
        "name": "KYC Issues",
        "description": "Agent faces difficulties with KYC/documentation requirements.",
        "detection_hints": [
            "KYC", "document", "Aadhaar", "PAN", "verification",
            "identity", "proof",
        ],
        "suggested_intervention_playbook": "training_gap_product_knowledge",
    },
    # ── PERSONAL ─────────────────────────────────────────────────────
    {
        "code": DormancyReasonCode.HEALTH_ISSUES,
        "parent_category": DormancyReasonCategory.PERSONAL,
        "name": "Health Issues",
        "description": "Agent is dealing with health problems that prevent active work.",
        "detection_hints": [
            "health", "sick", "hospital", "medical", "unwell",
            "treatment", "surgery",
        ],
        "suggested_intervention_playbook": "dormant_reengagement_generic",
    },
    {
        "code": DormancyReasonCode.RELOCATED,
        "parent_category": DormancyReasonCategory.PERSONAL,
        "name": "Relocated",
        "description": "Agent has moved to a different location and lost their network.",
        "detection_hints": [
            "moved", "relocated", "shifting", "new city",
            "different place", "transfer",
        ],
        "suggested_intervention_playbook": "dormant_reengagement_generic",
    },
    {
        "code": DormancyReasonCode.FAMILY_OBLIGATIONS,
        "parent_category": DormancyReasonCategory.PERSONAL,
        "name": "Family Obligations",
        "description": "Agent has family responsibilities limiting their availability.",
        "detection_hints": [
            "family", "children", "parents", "wedding", "personal",
            "home", "busy with family",
        ],
        "suggested_intervention_playbook": "dormant_reengagement_generic",
    },
    {
        "code": DormancyReasonCode.LOST_INTEREST,
        "parent_category": DormancyReasonCategory.PERSONAL,
        "name": "Lost Interest",
        "description": "Agent has lost interest in insurance as a career.",
        "detection_hints": [
            "not interested", "lost interest", "boring", "don't want",
            "quit", "leave", "give up",
        ],
        "suggested_intervention_playbook": "dormant_reengagement_generic",
    },
    {
        "code": DormancyReasonCode.OTHER_EMPLOYMENT,
        "parent_category": DormancyReasonCategory.PERSONAL,
        "name": "Other Employment",
        "description": "Agent has taken up another job (full-time or part-time).",
        "detection_hints": [
            "another job", "other work", "employment", "office job",
            "shop", "business", "full-time",
        ],
        "suggested_intervention_playbook": "dormant_reengagement_generic",
    },
    # ── REGULATORY ───────────────────────────────────────────────────
    {
        "code": DormancyReasonCode.LICENSE_EXPIRED,
        "parent_category": DormancyReasonCategory.REGULATORY,
        "name": "License Expired",
        "description": "Agent's IRDAI license has expired and they cannot sell.",
        "detection_hints": [
            "license expired", "IRDAI", "cannot sell", "expired",
            "renewal", "lapsed license",
        ],
        "suggested_intervention_playbook": "license_renewal_urgent",
    },
    {
        "code": DormancyReasonCode.LICENSE_EXPIRING_SOON,
        "parent_category": DormancyReasonCategory.REGULATORY,
        "name": "License Expiring Soon",
        "description": "Agent's license will expire within 60 days.",
        "detection_hints": [
            "expiring", "renew", "license renewal", "training hours",
            "CPD", "continuing education",
        ],
        "suggested_intervention_playbook": "license_renewal_urgent",
    },
    {
        "code": DormancyReasonCode.COMPLIANCE_ISSUE,
        "parent_category": DormancyReasonCategory.REGULATORY,
        "name": "Compliance Issue",
        "description": "Agent has compliance issues (mis-selling complaint, regulatory action).",
        "detection_hints": [
            "compliance", "mis-selling", "complaint", "IRDAI action",
            "penalty", "fine",
        ],
        "suggested_intervention_playbook": "dormant_reengagement_generic",
    },
    # ── UNKNOWN ──────────────────────────────────────────────────────
    {
        "code": DormancyReasonCode.UNKNOWN,
        "parent_category": DormancyReasonCategory.UNKNOWN,
        "name": "Unknown",
        "description": "Dormancy reason not yet identified. Needs voice AI interaction.",
        "detection_hints": [],
        "suggested_intervention_playbook": "dormant_reengagement_generic",
    },
]


def get_dormancy_taxonomy() -> list[dict]:
    """Return the full dormancy taxonomy."""
    return DORMANCY_TAXONOMY.copy()


def get_reasons_by_category(category: str) -> list[dict]:
    """Return all reasons for a given parent category."""
    return [r for r in DORMANCY_TAXONOMY if r["parent_category"] == category]
