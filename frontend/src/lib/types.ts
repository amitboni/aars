// TypeScript types matching backend Pydantic schemas

export type LifecycleState =
  | "onboarded"
  | "licensed"
  | "first_sale"
  | "active"
  | "productive"
  | "at_risk"
  | "dormant"
  | "lapsed"
  | "terminated";

export type ConsentStatus = "not_asked" | "granted" | "denied" | "revoked" | "expired";

export type DecisionAction =
  | "do_nothing"
  | "start_playbook"
  | "continue_playbook"
  | "send_nudge_to_adm"
  | "schedule_voice_call"
  | "send_whatsapp"
  | "send_training"
  | "escalate"
  | "celebrate"
  | "pause_outreach"
  | "close_and_archive";

export type UserRole =
  | "super_admin"
  | "tenant_admin"
  | "regional_manager"
  | "adm"
  | "compliance_officer"
  | "analyst"
  | "support_engineer";

export type AlertUrgency = "low" | "medium" | "high" | "critical";

export type ADMClassification = "HIGH_PERFORMER" | "AVERAGE" | "STRUGGLING" | "UNRESPONSIVE";

export interface Agent {
  id: string;
  tenant_id: string;
  agent_code: string;
  full_name: string;
  phone: string;
  email: string | null;
  lifecycle_state: LifecycleState;
  state_since: string;
  assigned_adm_id: string | null;
  engagement_score: number;
  last_positive_signal_at: string | null;
  last_contact_at: string | null;
  total_policies_sold: number;
  policies_sold_last_12m: number;
  dormancy_reason: string | null;
  license_number: string | null;
  license_expiry_date: string | null;
  consent_voice: ConsentStatus;
  consent_whatsapp: ConsentStatus;
  preferred_language: string;
  region_node_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Signal {
  id: string;
  tenant_id: string;
  signal_type: string;
  source: string;
  agent_id: string | null;
  adm_id: string | null;
  timestamp: string;
  channel: string | null;
  conversation_id: string | null;
  payload: Record<string, unknown>;
  metadata: Record<string, unknown>;
  idempotency_key: string | null;
  processed: boolean;
  processed_at: string | null;
  created_at: string;
}

export interface PlaybookStep {
  id: string;
  playbook_id: string;
  step_number: number;
  name: string;
  action_type: string;
  action_config: Record<string, unknown>;
  delay_days: number;
  next_step_rules: unknown[];
  created_at: string;
}

export interface Playbook {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  is_default: boolean;
  trigger_conditions: Record<string, unknown>;
  success_criteria: Record<string, unknown>;
  max_duration_days: number;
  times_executed: number;
  success_rate: number;
  steps: PlaybookStep[];
  created_at: string;
  updated_at: string;
}

export interface PlaybookSummary {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  is_default: boolean;
  max_duration_days: number;
  times_executed: number;
  success_rate: number;
  steps_count: number;
  created_at: string;
}

export interface PlaybookRun {
  id: string;
  tenant_id: string;
  playbook_id: string;
  agent_id: string;
  status: string;
  current_step_number: number;
  context: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
  next_step_due_at: string | null;
  outcome: string | null;
  steps_executed: number;
  created_at: string;
}

export interface DecisionLog {
  id: string;
  tenant_id: string;
  agent_id: string;
  adm_id: string | null;
  rule_id: string;
  decision_action: DecisionAction;
  playbook_id: string | null;
  channel: string | null;
  language: string | null;
  priority: string;
  reasoning: string;
  scheduled_time: string;
  executed: boolean;
  executed_at: string | null;
  execution_result: Record<string, unknown> | null;
  created_at: string;
}

export interface DashboardData {
  total_agents: number;
  active_agents: number;
  at_risk_agents: number;
  dormant_agents: number;
  agents_by_state: Record<string, number>;
  agent_activation_rate: number;
  agent_activation_trend: "up" | "down" | "stable";
  reactivation_count_this_month: number;
  reactivation_by_intervention: Record<string, number>;
}

export interface DormancyAnalytics {
  reason_distribution: Record<string, number>;
  top_growing_reason: string | null;
  top_shrinking_reason: string | null;
  trend_vs_last_month: Record<string, number>;
  regional_breakdown: Record<string, Record<string, number>>;
}

export interface ReactivationFunnel {
  contacted: number;
  engaged: number;
  trained: number;
  sold: number;
  conversion_rates: Record<string, number>;
  by_channel: Record<string, Record<string, number>>;
  by_playbook: Record<string, Record<string, number>>;
}

export interface ADMRanking {
  adm_id: string;
  name: string;
  total_agents: number;
  active_agents: number;
  activation_rate: number;
  nudge_response_rate: number;
  reactivations_last_90d: number;
  classification: ADMClassification;
}

export interface ADMPerformance {
  adm_rankings: ADMRanking[];
  top_5_adms: ADMRanking[];
  bottom_5_adms: ADMRanking[];
  average_activation_rate: number;
}

export interface TrainingEffectiveness {
  completion_rate_by_module: Record<string, number>;
  average_scores_by_module: Record<string, number>;
  training_to_sale_correlation: Record<string, number>;
  top_drop_off_modules: string[];
}

export interface SystemROI {
  new_premium_from_reactivated: number;
  system_cost_this_month: number;
  roi_multiplier: number;
  agents_reactivated: number;
  average_premium_per_reactivation: number;
}

export interface BriefingSnapshot {
  active_count: number;
  at_risk_count: number;
  at_risk_change: number;
  dormant_count: number;
}

export interface BriefingPriority {
  agent_id: string;
  agent_name: string;
  one_line_context: string;
  suggested_action: string;
  priority_emoji: string;
}

export interface BriefingCelebration {
  agent_id: string;
  agent_name: string;
  achievement: string;
}

export interface MorningBriefing {
  id: string;
  adm_id: string;
  briefing_date: string;
  snapshot: BriefingSnapshot;
  priorities: BriefingPriority[];
  celebrations: BriefingCelebration[];
  delivered_at: string | null;
  read_at: string | null;
}

export interface AlertItem {
  id: string;
  tenant_id: string;
  adm_id: string;
  agent_id: string;
  alert_type: string;
  urgency: string;
  message: string;
  delivered_at: string | null;
  read_at: string | null;
  acted_on_at: string | null;
  created_at: string;
}

export interface WeeklyWin {
  agent_name: string;
  achievement: string;
}

export interface WeeklyMovement {
  newly_active_count: number;
  newly_at_risk_count: number;
  reengaged_count: number;
}

export interface ADMNumbers {
  agents_contacted: number;
  system_assisted_contacts: number;
  training_completions: number;
}

export interface WeeklySummary {
  id: string;
  adm_id: string;
  week_start: string;
  week_end: string;
  wins: WeeklyWin[];
  movement: WeeklyMovement;
  adm_numbers: ADMNumbers;
  focus_areas: string[];
  delivered_at: string | null;
  read_at: string | null;
}

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  phone: string | null;
  roles: UserRole[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface PaginatedResponse<T> {
  data: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

// ─── Message Templates ──────────────────────────────────────────────────────

export interface MessageTemplate {
  id: string;
  tenant_id: string;
  name: string;
  category: string;
  description: string | null;
  language_variants: Record<string, string>;
  placeholders: string[];
  buttons: Record<string, unknown>[];
  status: string;
  version: number;
  previous_version_id: string | null;
  meta_template_id: string | null;
  is_default: boolean;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TemplateSummary {
  id: string;
  tenant_id: string;
  name: string;
  category: string;
  description: string | null;
  status: string;
  version: number;
  is_default: boolean;
  created_at: string;
}

export interface TemplateVersion {
  id: string;
  version: number;
  status: string;
  previous_version_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TemplatePreview {
  rendered: string;
  buttons: Record<string, unknown>[];
}

export interface TemplateCreatePayload {
  name: string;
  category: string;
  description?: string;
  language_variants?: Record<string, string>;
  placeholders?: string[];
  buttons?: Record<string, unknown>[];
  meta_template_id?: string;
}

export interface TemplateUpdatePayload {
  name?: string;
  category?: string;
  description?: string;
  language_variants?: Record<string, string>;
  placeholders?: string[];
  buttons?: Record<string, unknown>[];
  meta_template_id?: string;
}

// ─── Training ───────────────────────────────────────────────────────────────

export interface TrainingModule {
  id: string;
  tenant_id: string;
  title: string;
  description: string | null;
  topic: string;
  difficulty: string;
  duration_minutes: number;
  language: string;
  content_type: string;
  file_key: string | null;
  file_url: string | null;
  file_size_bytes: number | null;
  thumbnail_key: string | null;
  is_active: boolean;
  is_default: boolean;
  effectiveness_score: number;
  times_assigned: number;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TrainingModuleSummary {
  id: string;
  tenant_id: string;
  title: string;
  topic: string;
  difficulty: string;
  duration_minutes: number;
  is_active: boolean;
  is_default: boolean;
  times_assigned: number;
  created_at: string;
}

export interface TrainingModuleCreatePayload {
  title: string;
  description?: string;
  topic: string;
  difficulty?: string;
  duration_minutes: number;
  language?: string;
  content_type?: string;
  file_url?: string;
  expires_at?: string;
}

export interface TrainingModuleUpdatePayload {
  title?: string;
  description?: string;
  topic?: string;
  difficulty?: string;
  duration_minutes?: number;
  language?: string;
  content_type?: string;
  file_url?: string;
  is_active?: boolean;
  expires_at?: string;
}

export interface QuizQuestion {
  question: string;
  options: string[];
  correct: number;
  explanation?: string;
}

export interface Quiz {
  id: string;
  training_module_id: string;
  questions: QuizQuestion[];
  passing_score: number;
  max_attempts: number;
  created_at: string;
  updated_at: string;
}

export interface QuizCreatePayload {
  questions: QuizQuestion[];
  passing_score?: number;
  max_attempts?: number;
}

export interface TrainingProgress {
  id: string;
  tenant_id: string;
  training_module_id: string;
  agent_id: string;
  status: string;
  score: number | null;
  attempts: number;
  started_at: string | null;
  completed_at: string | null;
  assigned_by: string;
  playbook_run_id: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Settings ───────────────────────────────────────────────────────────────

export interface SettingsSection {
  values: Record<string, unknown>;
  metadata: Record<string, SettingFieldMetadata>;
}

export interface SettingFieldMetadata {
  type: string;
  description: string;
  min?: number;
  max?: number;
  allowed_values?: string[];
}

export type SettingsSectionName =
  | "lifecycle_thresholds"
  | "engagement_scoring_weights"
  | "contact_rules"
  | "trai_calling_hours"
  | "rate_limits"
  | "branding"
  | "languages";

export type AllSettings = Partial<Record<SettingsSectionName, SettingsSection>>;

export interface SettingsChangeRequestResponse {
  change_request_id: string;
  otp_sent_to: string;
  expires_at: string;
  changes_summary: Record<string, unknown>;
}

export interface SettingsAuditLogEntry {
  id: string;
  tenant_id: string;
  change_request_id: string;
  changed_by: string;
  changed_by_email: string;
  section: string;
  previous_values: Record<string, unknown>;
  new_values: Record<string, unknown>;
  changed_fields: string[];
  verified_at: string;
  applied_at: string;
  created_at: string;
}
