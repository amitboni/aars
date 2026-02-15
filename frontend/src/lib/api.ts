import axios from "axios";
import { getToken, removeToken } from "./auth";
import type {
  Agent,
  Signal,
  Playbook,
  PlaybookRun,
  DecisionLog,
  DashboardData,
  DormancyAnalytics,
  ReactivationFunnel,
  ADMPerformance,
  TrainingEffectiveness,
  SystemROI,
  MorningBriefing,
  AlertItem,
  AuthResponse,
  User,
  PaginatedResponse,
  PlaybookSummary,
  MessageTemplate,
  TemplateSummary,
  TemplateVersion,
  TemplatePreview,
  TemplateCreatePayload,
  TemplateUpdatePayload,
  TrainingModule,
  TrainingModuleSummary,
  TrainingModuleCreatePayload,
  TrainingModuleUpdatePayload,
  Quiz,
  QuizCreatePayload,
  TrainingProgress,
  AllSettings,
  SettingsSection,
  SettingsChangeRequestResponse,
  SettingsAuditLogEntry,
} from "./types";

const apiClient = axios.create({
  baseURL: "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      removeToken();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    const apiError = error.response?.data?.error;
    return Promise.reject(apiError ?? { code: "UNKNOWN", message: error.message, details: {} });
  }
);

interface ListParams {
  limit?: number;
  cursor?: string;
}

interface AgentListParams extends ListParams {
  lifecycle_state?: string;
  search?: string;
  adm_id?: string;
  region_node_id?: string;
}

interface SignalListParams extends ListParams {
  signal_type?: string;
  agent_id?: string;
  start_date?: string;
  end_date?: string;
}

interface AlertListParams extends ListParams {
  urgency?: string;
}

export const api = {
  auth: {
    login: async (email: string, password: string): Promise<AuthResponse> => {
      const { data } = await apiClient.post("/api/v1/auth/login", { email, password });
      return data;
    },
    me: async (): Promise<User> => {
      const { data } = await apiClient.get("/api/v1/auth/me");
      return data;
    },
  },

  agents: {
    list: async (params?: AgentListParams): Promise<PaginatedResponse<Agent>> => {
      const { data } = await apiClient.get("/api/v1/agents", { params });
      return data;
    },
    get: async (id: string): Promise<Agent> => {
      const { data } = await apiClient.get(`/api/v1/agents/${id}`);
      return data;
    },
    getSignals: async (id: string, params?: SignalListParams): Promise<PaginatedResponse<Signal>> => {
      const { data } = await apiClient.get(`/api/v1/agents/${id}/signals`, { params });
      return data;
    },
  },

  signals: {
    list: async (params?: SignalListParams): Promise<PaginatedResponse<Signal>> => {
      const { data } = await apiClient.get("/api/v1/signals", { params });
      return data;
    },
  },

  analytics: {
    dashboard: async (): Promise<DashboardData> => {
      const { data } = await apiClient.get("/api/v1/analytics/dashboard");
      return data;
    },
    dormancy: async (): Promise<DormancyAnalytics> => {
      const { data } = await apiClient.get("/api/v1/analytics/dormancy");
      return data;
    },
    reactivation: async (periodDays?: number): Promise<ReactivationFunnel> => {
      const { data } = await apiClient.get("/api/v1/analytics/reactivation-funnel", {
        params: periodDays ? { period_days: periodDays } : undefined,
      });
      return data;
    },
    admPerformance: async (): Promise<ADMPerformance> => {
      const { data } = await apiClient.get("/api/v1/analytics/adm-performance");
      return data;
    },
    trainingEffectiveness: async (): Promise<TrainingEffectiveness> => {
      const { data } = await apiClient.get("/api/v1/analytics/training-effectiveness");
      return data;
    },
    systemRoi: async (periodDays?: number, systemCost?: number): Promise<SystemROI> => {
      const params: Record<string, number> = {};
      if (periodDays) params.period_days = periodDays;
      if (systemCost) params.system_cost = systemCost;
      const { data } = await apiClient.get("/api/v1/analytics/system-roi", { params });
      return data;
    },
  },

  playbooks: {
    list: async (params?: ListParams): Promise<PaginatedResponse<PlaybookSummary>> => {
      const { data } = await apiClient.get("/api/v1/playbooks", { params });
      return data;
    },
    get: async (id: string): Promise<Playbook> => {
      const { data } = await apiClient.get(`/api/v1/playbooks/${id}`);
      return data;
    },
    trigger: async (playbookId: string, agentId: string): Promise<PlaybookRun> => {
      const { data } = await apiClient.post("/api/v1/playbooks/trigger", {
        playbook_id: playbookId,
        agent_id: agentId,
      });
      return data;
    },
    runs: async (params?: ListParams & { agent_id?: string; status?: string }): Promise<PaginatedResponse<PlaybookRun>> => {
      const { data } = await apiClient.get("/api/v1/playbooks/runs", { params });
      return data;
    },
  },

  decisions: {
    list: async (params?: ListParams & { agent_id?: string }): Promise<PaginatedResponse<DecisionLog>> => {
      const { data } = await apiClient.get("/api/v1/decisions", { params });
      return data;
    },
    evaluate: async (agentId: string): Promise<DecisionLog> => {
      const { data } = await apiClient.post(`/api/v1/decisions/evaluate/${agentId}`);
      return data;
    },
  },

  adm: {
    briefing: async (): Promise<MorningBriefing> => {
      const { data } = await apiClient.get("/api/v1/adm/briefing");
      return data;
    },
    alerts: async (params?: AlertListParams): Promise<PaginatedResponse<AlertItem>> => {
      const { data } = await apiClient.get("/api/v1/adm/alerts", { params });
      return data;
    },
  },

  templates: {
    list: async (params?: ListParams & { category?: string; status?: string }): Promise<PaginatedResponse<TemplateSummary>> => {
      const { data } = await apiClient.get("/api/v1/templates", { params });
      return data;
    },
    get: async (id: string): Promise<MessageTemplate> => {
      const { data } = await apiClient.get(`/api/v1/templates/${id}`);
      return data;
    },
    create: async (payload: TemplateCreatePayload): Promise<MessageTemplate> => {
      const { data } = await apiClient.post("/api/v1/templates", payload);
      return data;
    },
    update: async (id: string, payload: TemplateUpdatePayload): Promise<MessageTemplate> => {
      const { data } = await apiClient.put(`/api/v1/templates/${id}`, payload);
      return data;
    },
    delete: async (id: string): Promise<void> => {
      await apiClient.delete(`/api/v1/templates/${id}`);
    },
    approve: async (id: string): Promise<MessageTemplate> => {
      const { data } = await apiClient.post(`/api/v1/templates/${id}/approve`);
      return data;
    },
    activate: async (id: string): Promise<MessageTemplate> => {
      const { data } = await apiClient.post(`/api/v1/templates/${id}/activate`);
      return data;
    },
    archive: async (id: string): Promise<MessageTemplate> => {
      const { data } = await apiClient.post(`/api/v1/templates/${id}/archive`);
      return data;
    },
    versions: async (id: string): Promise<TemplateVersion[]> => {
      const { data } = await apiClient.get(`/api/v1/templates/${id}/versions`);
      return data;
    },
    preview: async (id: string, language: string, params: Record<string, string>): Promise<TemplatePreview> => {
      const { data } = await apiClient.post(`/api/v1/templates/${id}/preview`, { language, params });
      return data;
    },
  },

  training: {
    modules: {
      list: async (params?: ListParams & { topic?: string; difficulty?: string; is_active?: boolean }): Promise<PaginatedResponse<TrainingModuleSummary>> => {
        const { data } = await apiClient.get("/api/v1/training/modules", { params });
        return data;
      },
      get: async (id: string): Promise<TrainingModule> => {
        const { data } = await apiClient.get(`/api/v1/training/modules/${id}`);
        return data;
      },
      create: async (payload: TrainingModuleCreatePayload): Promise<TrainingModule> => {
        const { data } = await apiClient.post("/api/v1/training/modules", payload);
        return data;
      },
      update: async (id: string, payload: TrainingModuleUpdatePayload): Promise<TrainingModule> => {
        const { data } = await apiClient.put(`/api/v1/training/modules/${id}`, payload);
        return data;
      },
      delete: async (id: string): Promise<void> => {
        await apiClient.delete(`/api/v1/training/modules/${id}`);
      },
    },
    quiz: {
      get: async (moduleId: string): Promise<Quiz> => {
        const { data } = await apiClient.get(`/api/v1/training/modules/${moduleId}/quiz`);
        return data;
      },
      createOrUpdate: async (moduleId: string, payload: QuizCreatePayload): Promise<Quiz> => {
        const { data } = await apiClient.put(`/api/v1/training/modules/${moduleId}/quiz`, payload);
        return data;
      },
    },
    progress: {
      list: async (params?: ListParams & { agent_id?: string; module_id?: string; status?: string }): Promise<PaginatedResponse<TrainingProgress>> => {
        const { data } = await apiClient.get("/api/v1/training/progress", { params });
        return data;
      },
    },
  },

  settings: {
    getAll: async (): Promise<AllSettings> => {
      const { data } = await apiClient.get("/api/v1/settings");
      return data;
    },
    getSection: async (section: string): Promise<SettingsSection> => {
      const { data } = await apiClient.get(`/api/v1/settings/${section}`);
      return data;
    },
    requestChange: async (section: string, changes: Record<string, unknown>): Promise<SettingsChangeRequestResponse> => {
      const { data } = await apiClient.post(`/api/v1/settings/${section}/request-change`, { changes });
      return data;
    },
    verifyOtp: async (changeRequestId: string, otp: string): Promise<SettingsAuditLogEntry> => {
      const { data } = await apiClient.post("/api/v1/settings/verify-otp", { change_request_id: changeRequestId, otp });
      return data;
    },
    cancelRequest: async (section: string, changeRequestId: string): Promise<void> => {
      await apiClient.post(`/api/v1/settings/${section}/request-change/cancel`, { change_request_id: changeRequestId });
    },
    auditLog: async (params?: ListParams & { section?: string }): Promise<PaginatedResponse<SettingsAuditLogEntry>> => {
      const { data } = await apiClient.get("/api/v1/settings/audit-log", { params });
      return data;
    },
  },
};
