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
};
