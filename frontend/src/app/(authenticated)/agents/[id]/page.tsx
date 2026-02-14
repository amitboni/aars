"use client";

import React, { useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Tabs } from "@/components/ui/Tabs";
import { EngagementGauge } from "@/components/ui/EngagementGauge";
import { SignalIcon, getSignalCategory } from "@/components/ui/SignalIcon";
import { Pagination } from "@/components/ui/Pagination";
import { FilterSelect } from "@/components/ui/FilterBar";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import {
  formatDate,
  formatDateTime,
  formatRelativeTime,
  maskPhone,
  daysAgo,
  cn,
} from "@/lib/utils";
import type { Agent, Signal, DecisionLog, PlaybookRun } from "@/lib/types";
import { ArrowLeft, Check, ChevronDown, ChevronUp, Clock } from "lucide-react";

// --- Shared helpers ---

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between py-2 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="text-right font-medium text-gray-900">{value ?? "—"}</span>
    </div>
  );
}

const CONSENT_CHANNELS = [
  { key: "consent_voice" as const, label: "Voice" },
  { key: "consent_whatsapp" as const, label: "WhatsApp" },
];

// --- Overview Tab ---

function OverviewTab({ agent }: { agent: Agent }) {
  const stateSinceDays = daysAgo(agent.state_since);

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <p className="text-xs text-gray-500">Total Policies</p>
          <p className="mt-1 text-xl font-bold text-gray-900">
            {agent.total_policies_sold}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-gray-500">Policies (12m)</p>
          <p className="mt-1 text-xl font-bold text-gray-900">
            {agent.policies_sold_last_12m}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-gray-500">Days in State</p>
          <p className="mt-1 text-xl font-bold text-gray-900">
            {stateSinceDays}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-gray-500">Engagement</p>
          <p className="mt-1 text-xl font-bold text-gray-900">
            {agent.engagement_score.toFixed(0)}
          </p>
        </Card>
      </div>

      {/* Dormancy Reason */}
      {agent.dormancy_reason && (
        <Card title="Dormancy Reason">
          <Badge variant="danger" className="text-sm">
            {agent.dormancy_reason.replace(/_/g, " ")}
          </Badge>
        </Card>
      )}

      {/* Info panels */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card title="Contact Info">
          <div className="divide-y divide-gray-100">
            <InfoRow label="Phone" value={maskPhone(agent.phone)} />
            <InfoRow label="Email" value={agent.email} />
            <InfoRow label="Language" value={agent.preferred_language} />
            <InfoRow
              label="Last Contact"
              value={formatRelativeTime(agent.last_contact_at)}
            />
          </div>
        </Card>

        <Card title="Sales & License">
          <div className="divide-y divide-gray-100">
            <InfoRow label="Total Policies" value={agent.total_policies_sold} />
            <InfoRow label="Policies (12m)" value={agent.policies_sold_last_12m} />
            <InfoRow label="License #" value={agent.license_number} />
            <InfoRow
              label="License Expiry"
              value={formatDate(agent.license_expiry_date)}
            />
          </div>
        </Card>

        <Card title="ADM Assignment">
          <div className="divide-y divide-gray-100">
            <InfoRow
              label="ADM ID"
              value={
                agent.assigned_adm_id
                  ? agent.assigned_adm_id.slice(0, 8) + "..."
                  : "Unassigned"
              }
            />
            <InfoRow
              label="State Since"
              value={formatDate(agent.state_since)}
            />
          </div>
        </Card>

        <Card title="Consent Status">
          <div className="divide-y divide-gray-100">
            {CONSENT_CHANNELS.map(({ key, label }) => (
              <InfoRow
                key={key}
                label={label}
                value={
                  <Badge
                    variant={
                      agent[key] === "granted"
                        ? "success"
                        : agent[key] === "denied" || agent[key] === "revoked"
                        ? "danger"
                        : "default"
                    }
                  >
                    {agent[key]}
                  </Badge>
                }
              />
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

// --- Signals Tab ---

function SignalsTab({ agentId }: { agentId: string }) {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [cursor, setCursor] = useState<string | undefined>();
  const [loadingMore, setLoadingMore] = useState(false);
  const [signalTypeFilter, setSignalTypeFilter] = useState("");

  const { data, isLoading } = useApi(
    () =>
      api.agents.getSignals(agentId, {
        limit: 20,
        signal_type: signalTypeFilter || undefined,
      }),
    [agentId, signalTypeFilter]
  );

  React.useEffect(() => {
    if (data) {
      setSignals(data.data);
      setCursor(data.next_cursor ?? undefined);
    }
  }, [data]);

  const loadMore = useCallback(async () => {
    if (!cursor) return;
    setLoadingMore(true);
    try {
      const more = await api.agents.getSignals(agentId, {
        cursor,
        limit: 20,
        signal_type: signalTypeFilter || undefined,
      });
      setSignals((prev) => [...prev, ...more.data]);
      setCursor(more.next_cursor ?? undefined);
    } finally {
      setLoadingMore(false);
    }
  }, [agentId, cursor, signalTypeFilter]);

  const SIGNAL_TYPE_OPTIONS = [
    { value: "policy_sold", label: "Policy Sold" },
    { value: "lifecycle_state_changed", label: "State Changed" },
    { value: "voice_call_outcome", label: "Voice Call" },
    { value: "whatsapp_agent_replied", label: "WhatsApp Reply" },
    { value: "training_completed_external", label: "Training" },
    { value: "adm_nudge_acted_on", label: "Nudge Acted On" },
  ];

  return (
    <div className="space-y-4">
      <FilterSelect
        label="All Signal Types"
        value={signalTypeFilter}
        options={SIGNAL_TYPE_OPTIONS}
        onChange={setSignalTypeFilter}
      />

      {isLoading ? (
        <LoadingSpinner text="Loading signals..." />
      ) : signals.length === 0 ? (
        <EmptyState message="No signals recorded" />
      ) : (
        <>
          <div className="space-y-2">
            {signals.map((s) => (
              <div
                key={s.id}
                className="flex items-start gap-3 rounded-lg border border-gray-100 bg-white p-3"
              >
                <SignalIcon signalType={s.signal_type} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">
                      {s.signal_type.replace(/_/g, " ")}
                    </span>
                    <Badge variant="default" className="text-[10px]">
                      {getSignalCategory(s.signal_type)}
                    </Badge>
                    {s.channel && (
                      <Badge variant="info" className="text-[10px]">
                        {s.channel.replace(/_/g, " ")}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-gray-400">
                    {s.source}
                  </p>
                  {/* Show key payload data */}
                  {Object.keys(s.payload).length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                      {Object.entries(s.payload)
                        .slice(0, 3)
                        .map(([k, v]) => (
                          <span key={k}>
                            {k.replace(/_/g, " ")}:{" "}
                            <strong>{String(v)}</strong>
                          </span>
                        ))}
                    </div>
                  )}
                </div>
                <span className="flex-shrink-0 text-xs text-gray-400">
                  {formatDateTime(s.timestamp)}
                </span>
              </div>
            ))}
          </div>
          <Pagination
            hasMore={!!cursor}
            isLoading={loadingMore}
            onLoadMore={loadMore}
            count={signals.length}
          />
        </>
      )}
    </div>
  );
}

// --- Decisions Tab ---

const PRIORITY_VARIANT: Record<string, "danger" | "warning" | "info" | "default"> = {
  critical: "danger",
  high: "warning",
  medium: "info",
  low: "default",
};

function DecisionsTab({ agentId }: { agentId: string }) {
  const [decisions, setDecisions] = useState<DecisionLog[]>([]);
  const [cursor, setCursor] = useState<string | undefined>();
  const [loadingMore, setLoadingMore] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useApi(
    () => api.decisions.list({ agent_id: agentId, limit: 20 }),
    [agentId]
  );

  React.useEffect(() => {
    if (data) {
      setDecisions(data.data);
      setCursor(data.next_cursor ?? undefined);
    }
  }, [data]);

  const loadMore = useCallback(async () => {
    if (!cursor) return;
    setLoadingMore(true);
    try {
      const more = await api.decisions.list({ agent_id: agentId, cursor, limit: 20 });
      setDecisions((prev) => [...prev, ...more.data]);
      setCursor(more.next_cursor ?? undefined);
    } finally {
      setLoadingMore(false);
    }
  }, [agentId, cursor]);

  if (isLoading) return <LoadingSpinner text="Loading decisions..." />;
  if (decisions.length === 0) return <EmptyState message="No decisions for this agent" />;

  return (
    <div className="space-y-2">
      {decisions.map((d) => (
        <div
          key={d.id}
          className="rounded-lg border border-gray-100 bg-white p-4"
        >
          <div className="flex items-start justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="info">
                {d.decision_action.replace(/_/g, " ")}
              </Badge>
              <Badge variant={PRIORITY_VARIANT[d.priority] ?? "default"}>
                {d.priority}
              </Badge>
              <span className="text-xs text-gray-500">Rule: {d.rule_id}</span>
            </div>
            <div className="flex items-center gap-2">
              {d.executed ? (
                <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                  <Check className="h-3.5 w-3.5" /> Executed
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs text-gray-400">
                  <Clock className="h-3.5 w-3.5" /> Pending
                </span>
              )}
            </div>
          </div>
          <div className="mt-2">
            <p className={cn("text-sm text-gray-700", expandedId !== d.id && "line-clamp-2")}>
              {d.reasoning}
            </p>
            {d.reasoning.length > 120 && (
              <button
                onClick={() => setExpandedId(expandedId === d.id ? null : d.id)}
                className="mt-1 inline-flex items-center text-xs text-blue-600 hover:text-blue-800"
              >
                {expandedId === d.id ? (
                  <>
                    Show less <ChevronUp className="ml-0.5 h-3 w-3" />
                  </>
                ) : (
                  <>
                    Show more <ChevronDown className="ml-0.5 h-3 w-3" />
                  </>
                )}
              </button>
            )}
          </div>
          <p className="mt-2 text-xs text-gray-400">
            {formatDateTime(d.created_at)}
            {d.executed_at && <> &middot; Executed {formatRelativeTime(d.executed_at)}</>}
          </p>
        </div>
      ))}
      <Pagination
        hasMore={!!cursor}
        isLoading={loadingMore}
        onLoadMore={loadMore}
        count={decisions.length}
      />
    </div>
  );
}

// --- Playbooks Tab ---

function PlaybooksTab({ agentId }: { agentId: string }) {
  const { data, isLoading } = useApi(
    () => api.playbooks.runs({ agent_id: agentId, limit: 20 }),
    [agentId]
  );

  if (isLoading) return <LoadingSpinner text="Loading playbook runs..." />;

  const runs = data?.data ?? [];
  const activeRuns = runs.filter((r) => r.status === "running" || r.status === "pending");
  const completedRuns = runs.filter((r) => r.status !== "running" && r.status !== "pending");

  if (runs.length === 0) {
    return <EmptyState message="No playbook runs for this agent" />;
  }

  return (
    <div className="space-y-6">
      {activeRuns.length > 0 && (
        <div>
          <h4 className="mb-3 text-sm font-semibold text-gray-900">
            Active Runs ({activeRuns.length})
          </h4>
          <div className="space-y-2">
            {activeRuns.map((run) => (
              <PlaybookRunCard key={run.id} run={run} />
            ))}
          </div>
        </div>
      )}

      {completedRuns.length > 0 && (
        <div>
          <h4 className="mb-3 text-sm font-semibold text-gray-900">
            History ({completedRuns.length})
          </h4>
          <div className="space-y-2">
            {completedRuns.map((run) => (
              <PlaybookRunCard key={run.id} run={run} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PlaybookRunCard({ run }: { run: PlaybookRun }) {
  const statusVariant: Record<string, "success" | "warning" | "info" | "danger" | "default"> = {
    completed: "success",
    running: "info",
    pending: "default",
    failed: "danger",
    cancelled: "warning",
  };

  return (
    <div className="rounded-lg border border-gray-100 bg-white p-4">
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs font-mono text-gray-400">
            {run.playbook_id.slice(0, 8)}...
          </span>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant={statusVariant[run.status] ?? "default"}>
              {run.status}
            </Badge>
            <span className="text-xs text-gray-500">
              Step {run.current_step_number} &middot; {run.steps_executed} steps executed
            </span>
          </div>
        </div>
        {run.outcome && (
          <Badge variant={run.outcome === "success" ? "success" : "default"}>
            {run.outcome}
          </Badge>
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-500">
        <span>Started: {formatDate(run.started_at)}</span>
        {run.completed_at && <span>Completed: {formatDate(run.completed_at)}</span>}
        {run.next_step_due_at && (
          <span>Next step due: {formatRelativeTime(run.next_step_due_at)}</span>
        )}
      </div>
    </div>
  );
}

// --- Main Page ---

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [activeTab, setActiveTab] = useState("overview");

  const {
    data: agent,
    isLoading: agentLoading,
    error: agentError,
  } = useApi(() => api.agents.get(id), [id]);

  if (agentLoading) return <LoadingSpinner text="Loading agent..." />;
  if (agentError) {
    return (
      <div className="flex flex-col items-center py-20">
        <p className="text-red-600">Failed to load agent: {agentError}</p>
        <button
          onClick={() => router.push("/agents")}
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          Back to agents
        </button>
      </div>
    );
  }
  if (!agent) return null;

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "signals", label: "Signals" },
    { id: "decisions", label: "Decisions" },
    { id: "playbooks", label: "Playbooks" },
  ];

  return (
    <div className="space-y-6">
      {/* Back + Header */}
      <button
        onClick={() => router.push("/agents")}
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Agents
      </button>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {agent.full_name}
            </h1>
            <div className="mt-1 flex items-center gap-2 text-sm text-gray-500">
              <span className="font-mono">{agent.agent_code}</span>
              <span>&middot;</span>
              <span>{maskPhone(agent.phone)}</span>
            </div>
          </div>
          <Badge
            variant="lifecycle"
            lifecycleState={agent.lifecycle_state}
            className="text-sm px-3 py-1"
          >
            {agent.lifecycle_state.replace(/_/g, " ")}
          </Badge>
          <span className="text-xs text-gray-400">
            {daysAgo(agent.state_since)}d in state
          </span>
        </div>
        <EngagementGauge score={agent.engagement_score} size="lg" />
      </div>

      {/* Tabs */}
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {/* Tab Content */}
      <div>
        {activeTab === "overview" && <OverviewTab agent={agent} />}
        {activeTab === "signals" && <SignalsTab agentId={id} />}
        {activeTab === "decisions" && <DecisionsTab agentId={id} />}
        {activeTab === "playbooks" && <PlaybooksTab agentId={id} />}
      </div>
    </div>
  );
}
