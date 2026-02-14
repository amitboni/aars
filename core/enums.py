"""core/enums.py — All domain enums. Central location."""
from enum import StrEnum


class AgentLifecycleState(StrEnum):
    ONBOARDED = "onboarded"
    LICENSED = "licensed"
    FIRST_SALE = "first_sale"
    ACTIVE = "active"
    PRODUCTIVE = "productive"
    AT_RISK = "at_risk"
    DORMANT = "dormant"
    LAPSED = "lapsed"
    TERMINATED = "terminated"


class ChannelType(StrEnum):
    VOICE_AI = "voice_ai"
    WHATSAPP_BOT = "whatsapp_bot"
    WHATSAPP_ADM = "whatsapp_adm"
    ADM_CALL = "adm_call"
    ADM_VISIT = "adm_visit"
    SMS = "sms"
    EMAIL = "email"
    SELF_SERVICE = "self_service"


class ContactOutcome(StrEnum):
    ANSWERED = "answered"
    NOT_ANSWERED = "not_answered"
    BUSY = "busy"
    SWITCHED_OFF = "switched_off"
    WRONG_NUMBER = "wrong_number"
    DND_BLOCKED = "dnd_blocked"
    OPTED_OUT = "opted_out"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED_TECHNICAL = "failed_technical"


class ConsentStatus(StrEnum):
    NOT_ASKED = "not_asked"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"
    INTERESTED = "interested"
    CONFUSED = "confused"


class SignalSource(StrEnum):
    """What system or actor generated this signal."""
    VOICE_AI = "voice_ai"
    WHATSAPP_BOT = "whatsapp_bot"
    ADM_REPORT = "adm_report"
    PAS_SYNC = "pas_sync"
    LMS_SYNC = "lms_sync"
    COMMISSION_SYNC = "commission_sync"
    SYSTEM = "system"
    MANUAL = "manual"
    BATCH_IMPORT = "batch_import"


class SignalType(StrEnum):
    # Voice AI
    VOICE_CALL_INITIATED = "voice_call_initiated"
    VOICE_CALL_OUTCOME = "voice_call_outcome"
    VOICE_CONVERSATION_ANALYZED = "voice_conversation_analyzed"
    VOICE_CALL_RECORDING_STORED = "voice_call_recording_stored"
    # WhatsApp
    WHATSAPP_MESSAGE_SENT = "whatsapp_message_sent"
    WHATSAPP_MESSAGE_DELIVERED = "whatsapp_message_delivered"
    WHATSAPP_MESSAGE_READ = "whatsapp_message_read"
    WHATSAPP_AGENT_REPLIED = "whatsapp_agent_replied"
    WHATSAPP_TRAINING_INTERACTION = "whatsapp_training_interaction"
    # ADM Activity
    ADM_AGENT_CALL_LOGGED = "adm_agent_call_logged"
    ADM_AGENT_VISIT_LOGGED = "adm_agent_visit_logged"
    ADM_NUDGE_RECEIVED = "adm_nudge_received"
    ADM_NUDGE_ACTED_ON = "adm_nudge_acted_on"
    ADM_BRIEFING_OPENED = "adm_briefing_opened"
    # Business Events
    POLICY_SOLD = "policy_sold"
    COMMISSION_CREDITED = "commission_credited"
    LICENSE_STATUS_CHANGED = "license_status_changed"
    AGENT_DATA_UPDATED = "agent_data_updated"
    TRAINING_COMPLETED_EXTERNAL = "training_completed_external"
    # System Events
    LIFECYCLE_STATE_CHANGED = "lifecycle_state_changed"
    PLAYBOOK_STARTED = "playbook_started"
    PLAYBOOK_STEP_EXECUTED = "playbook_step_executed"
    PLAYBOOK_COMPLETED = "playbook_completed"
    ESCALATION_CREATED = "escalation_created"
    CONSENT_CHANGED = "consent_changed"


class CallPurpose(StrEnum):
    """Purpose of a voice AI call."""
    CHECK_IN = "check_in"
    TRAINING = "training"
    REACTIVATION = "reactivation"
    CONGRATULATION = "congratulation"
    SURVEY = "survey"
    LICENSE_RENEWAL = "license_renewal"
    FIRST_CONTACT = "first_contact"


class DormancyReasonCategory(StrEnum):
    TRAINING_GAP = "training_gap"
    ENGAGEMENT_GAP = "engagement_gap"
    ECONOMIC = "economic"
    OPERATIONAL = "operational"
    PERSONAL = "personal"
    REGULATORY = "regulatory"
    UNKNOWN = "unknown"


class DormancyReasonCode(StrEnum):
    PRODUCT_KNOWLEDGE_INSUFFICIENT = "training_gap.product_knowledge_insufficient"
    SALES_SKILLS_LACKING = "training_gap.sales_skills_lacking"
    EXAM_NOT_ATTEMPTED = "training_gap.exam_not_attempted"
    EXAM_FAILED = "training_gap.exam_failed"
    PROCESS_UNCLEAR = "training_gap.process_unclear"
    ADM_NEVER_CONTACTED = "engagement_gap.adm_never_contacted"
    ADM_NO_FOLLOWTHROUGH = "engagement_gap.adm_no_followthrough"
    FEELS_UNSUPPORTED = "engagement_gap.feels_unsupported"
    NO_RECOGNITION = "engagement_gap.no_recognition"
    COMMISSION_TOO_LOW = "economic.commission_too_low"
    COMPETITOR_BETTER_COMMISSION = "economic.competitor_better_commission"
    IRREGULAR_PAYMENTS = "economic.irregular_payments"
    INSUFFICIENT_INCOME = "economic.insufficient_income"
    PROPOSAL_PROCESS_COMPLEX = "operational.proposal_process_complex"
    TECHNOLOGY_BARRIERS = "operational.technology_barriers"
    CLAIM_EXPERIENCE_BAD = "operational.claim_experience_bad"
    SLOW_ISSUANCE = "operational.slow_issuance"
    KYC_ISSUES = "operational.kyc_issues"
    HEALTH_ISSUES = "personal.health_issues"
    RELOCATED = "personal.relocated"
    FAMILY_OBLIGATIONS = "personal.family_obligations"
    LOST_INTEREST = "personal.lost_interest"
    OTHER_EMPLOYMENT = "personal.other_employment"
    LICENSE_EXPIRED = "regulatory.license_expired"
    LICENSE_EXPIRING_SOON = "regulatory.license_expiring_soon"
    COMPLIANCE_ISSUE = "regulatory.compliance_issue"
    UNKNOWN = "unknown"


class TrainingTopic(StrEnum):
    """Training content topic categories."""
    PRODUCT_TERM_LIFE = "product_term_life"
    PRODUCT_ENDOWMENT = "product_endowment"
    PRODUCT_ULIP = "product_ulip"
    PRODUCT_HEALTH = "product_health"
    PRODUCT_PENSION = "product_pension"
    SALES_PROSPECTING = "sales_prospecting"
    SALES_PITCH = "sales_pitch"
    SALES_OBJECTION_HANDLING = "sales_objection_handling"
    SALES_CLOSING = "sales_closing"
    PROCESS_PROPOSAL_FILLING = "process_proposal_filling"
    PROCESS_KYC = "process_kyc"
    PROCESS_DIGITAL_TOOLS = "process_digital_tools"
    COMPLIANCE_BASICS = "compliance_basics"
    COMPLIANCE_MIS_SELLING = "compliance_mis_selling"
    SOFT_SKILLS_COMMUNICATION = "soft_skills_communication"
    SOFT_SKILLS_TRUST_BUILDING = "soft_skills_trust_building"


class PlaybookActionType(StrEnum):
    VOICE_CALL = "voice_call"
    WHATSAPP_MESSAGE = "whatsapp_message"
    WHATSAPP_TRAINING = "whatsapp_training"
    ADM_NUDGE = "adm_nudge"
    WAIT = "wait"
    ESCALATE = "escalate"


class DecisionAction(StrEnum):
    DO_NOTHING = "do_nothing"
    START_PLAYBOOK = "start_playbook"
    CONTINUE_PLAYBOOK = "continue_playbook"
    SEND_NUDGE_TO_ADM = "send_nudge_to_adm"
    SCHEDULE_VOICE_CALL = "schedule_voice_call"
    SEND_WHATSAPP = "send_whatsapp"
    SEND_TRAINING = "send_training"
    ESCALATE = "escalate"
    CELEBRATE = "celebrate"
    PAUSE_OUTREACH = "pause_outreach"
    CLOSE_AND_ARCHIVE = "close_and_archive"


class RegionHierarchyLevel(StrEnum):
    ZONE = "zone"
    REGION = "region"
    BRANCH = "branch"
    AREA = "area"


class SubscriptionTier(StrEnum):
    TRIAL = "trial"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    REGIONAL_MANAGER = "regional_manager"
    ADM = "adm"
    COMPLIANCE_OFFICER = "compliance_officer"
    ANALYST = "analyst"
    SUPPORT_ENGINEER = "support_engineer"


class ProductCategory(StrEnum):
    TERM_LIFE = "term_life"
    ENDOWMENT = "endowment"
    ULIP = "ulip"
    WHOLE_LIFE = "whole_life"
    PENSION = "pension"
    HEALTH = "health"
    GROUP = "group"
