"use client";

import React, { useState, useCallback, useMemo } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Pagination } from "@/components/ui/Pagination";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatCard } from "@/components/ui/StatCard";
import { FilterBar, FilterSelect } from "@/components/ui/FilterBar";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatDateTime, formatNumber, cn } from "@/lib/utils";
import type { DecisionLog } from "@/lib/types";
import {
  Check,
  Clock,
  ChevronDown,
  ChevronUp,
  Scale,
  AlertTriangle,
} from "lucide-react";

const PRIORITY_VARIANT: Record<string, "danger" | "warning" | "info" | "default"> = {
  critical: "danger",
  high: "warning",
  medium: "info",
  low: "default",
};

const ACTION_OPTIONS = [
  { value: "do_nothing", label: "Do Nothing" },
  { value: "start_playbook", label: "Start Playbook" },
  { value: "continue_playbook", label: "Continue Playbook" },
  { value: "send_nudge_to_adm", label: "Nudge ADM" },
  { value: "schedule_voice_call", label: "Voice Call" },
  { value: "send_whatsapp", label: "WhatsApp" },
  { value: "send_training", label: "Training" },
  { value: "escalate", label: "Escalate" },
  { value: "celebrate", label: "Celebrate" },
  { value: "pause_outreach", label: "Pause Outreach" },
  { value: "close_and_archive", label: "Close & Archive" },
];

const PRIORITY_OPTIONS = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const EXECUTED_OPTIONS = [
  { value: "true", label: "Executed" },
  { value: "false", label: "Pending" },
];

export default function DecisionsPage() {
  const [decisions, setDecisions] = useState<DecisionLog[]>([]);
  const [cursor, setCursor] = useState<string | undefined>();
  const [loadingMore, setLoadingMore] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Filters (client-side since backend only supports agent_id filter)
  const [actionFilter, setActionFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [executedFilter, setExecutedFilter] = useState("");

  const { data, isLoading, error } = useApi(
    () => api.decisions.list({ limit: 100 }),
    []
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
      const more = await api.decisions.list({ cursor, limit: 100 });
      setDecisions((prev) => [...prev, ...more.data]);
      setCursor(more.next_cursor ?? undefined);
    } finally {
      setLoadingMore(false);
    }
  }, [cursor]);

  const filtered = useMemo(() => {
    let result = decisions;
    if (actionFilter) result = result.filter((d) => d.decision_action === actionFilter);
    if (priorityFilter) result = result.filter((d) => d.priority === priorityFilter);
    if (executedFilter) result = result.filter((d) => String(d.executed) === executedFilter);
    return result;
  }, [decisions, actionFilter, priorityFilter, executedFilter]);

  // Stats
  const stats = useMemo(() => {
    const total = decisions.length;
    const executed = decisions.filter((d) => d.executed).length;
    const pending = total - executed;
    const critical = decisions.filter((d) => d.priority === "critical").length;
    const high = decisions.filter((d) => d.priority === "high").length;
    return { total, executed, pending, critical, high };
  }, [decisions]);

  if (isLoading) return <LoadingSpinner text="Loading decisions..." />;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Decision Log</h1>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard
          label="Total Decisions"
          value={formatNumber(stats.total)}
          icon={<Scale className="h-5 w-5" />}
        />
        <StatCard
          label="Executed"
          value={formatNumber(stats.executed)}
          icon={<Check className="h-5 w-5" />}
          trend={stats.total > 0 ? {
            direction: stats.executed / stats.total > 0.5 ? "up" : "down",
            label: `${Math.round((stats.executed / stats.total) * 100)}% rate`,
          } : undefined}
        />
        <StatCard
          label="Pending"
          value={formatNumber(stats.pending)}
          icon={<Clock className="h-5 w-5" />}
        />
        <StatCard
          label="Critical + High"
          value={formatNumber(stats.critical + stats.high)}
          icon={<AlertTriangle className="h-5 w-5" />}
          subtitle={`${stats.critical} critical, ${stats.high} high`}
        />
      </div>

      {/* Filters */}
      <FilterBar>
        <FilterSelect
          label="Action Type"
          value={actionFilter}
          options={ACTION_OPTIONS}
          onChange={setActionFilter}
        />
        <FilterSelect
          label="Priority"
          value={priorityFilter}
          options={PRIORITY_OPTIONS}
          onChange={setPriorityFilter}
        />
        <FilterSelect
          label="Status"
          value={executedFilter}
          options={EXECUTED_OPTIONS}
          onChange={setExecutedFilter}
        />
        {(actionFilter || priorityFilter || executedFilter) && (
          <button
            onClick={() => {
              setActionFilter("");
              setPriorityFilter("");
              setExecutedFilter("");
            }}
            className="text-xs text-blue-600 hover:text-blue-800"
          >
            Clear filters
          </button>
        )}
        <span className="ml-auto text-xs text-gray-400">
          {filtered.length} of {decisions.length} shown
        </span>
      </FilterBar>

      {/* Decision List */}
      {filtered.length === 0 ? (
        <EmptyState message="No decisions match the current filters" />
      ) : (
        <div className="space-y-2">
          {filtered.map((d) => {
            const isExpanded = expandedId === d.id;
            return (
              <Card key={d.id} className="p-0">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : d.id)}
                  className="w-full text-left"
                >
                  <div className="flex items-center gap-3 px-4 py-3">
                    {/* Executed indicator */}
                    <div className={cn(
                      "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full",
                      d.executed ? "bg-emerald-50" : "bg-gray-100"
                    )}>
                      {d.executed ? (
                        <Check className="h-4 w-4 text-emerald-500" />
                      ) : (
                        <Clock className="h-4 w-4 text-gray-400" />
                      )}
                    </div>

                    {/* Main content */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="info">
                          {d.decision_action.replace(/_/g, " ")}
                        </Badge>
                        <Badge variant={PRIORITY_VARIANT[d.priority] ?? "default"}>
                          {d.priority}
                        </Badge>
                        <span className="text-xs text-gray-400">
                          Rule: {d.rule_id}
                        </span>
                      </div>
                      <p className="mt-1 truncate text-sm text-gray-600">
                        {d.reasoning}
                      </p>
                    </div>

                    {/* Right side */}
                    <div className="flex flex-shrink-0 items-center gap-3">
                      <span className="text-xs text-gray-400">
                        {formatDateTime(d.created_at)}
                      </span>
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4 text-gray-400" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      )}
                    </div>
                  </div>
                </button>

                {/* Expanded Detail */}
                {isExpanded && (
                  <div className="border-t border-gray-100 bg-gray-50 px-4 py-4">
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <div>
                        <h4 className="text-xs font-semibold uppercase text-gray-500">
                          Full Reasoning
                        </h4>
                        <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">
                          {d.reasoning}
                        </p>
                      </div>
                      <div className="space-y-3">
                        <div>
                          <span className="text-xs font-semibold uppercase text-gray-500">
                            Agent ID
                          </span>
                          <p className="mt-0.5 font-mono text-xs text-gray-700">
                            {d.agent_id}
                          </p>
                        </div>
                        {d.adm_id && (
                          <div>
                            <span className="text-xs font-semibold uppercase text-gray-500">
                              ADM ID
                            </span>
                            <p className="mt-0.5 font-mono text-xs text-gray-700">
                              {d.adm_id}
                            </p>
                          </div>
                        )}
                        {d.playbook_id && (
                          <div>
                            <span className="text-xs font-semibold uppercase text-gray-500">
                              Playbook ID
                            </span>
                            <p className="mt-0.5 font-mono text-xs text-gray-700">
                              {d.playbook_id}
                            </p>
                          </div>
                        )}
                        {d.channel && (
                          <div>
                            <span className="text-xs font-semibold uppercase text-gray-500">
                              Channel
                            </span>
                            <p className="mt-0.5 text-sm capitalize text-gray-700">
                              {d.channel}
                            </p>
                          </div>
                        )}
                        <div>
                          <span className="text-xs font-semibold uppercase text-gray-500">
                            Scheduled Time
                          </span>
                          <p className="mt-0.5 text-sm text-gray-700">
                            {formatDateTime(d.scheduled_time)}
                          </p>
                        </div>
                        {d.executed && d.executed_at && (
                          <div>
                            <span className="text-xs font-semibold uppercase text-gray-500">
                              Executed At
                            </span>
                            <p className="mt-0.5 text-sm text-gray-700">
                              {formatDateTime(d.executed_at)}
                            </p>
                          </div>
                        )}
                        {d.execution_result && Object.keys(d.execution_result).length > 0 && (
                          <div>
                            <span className="text-xs font-semibold uppercase text-gray-500">
                              Execution Result
                            </span>
                            <pre className="mt-0.5 overflow-auto rounded bg-white p-2 text-xs text-gray-700">
                              {JSON.stringify(d.execution_result, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      <Pagination
        hasMore={!!cursor}
        isLoading={loadingMore}
        onLoadMore={loadMore}
        count={decisions.length}
      />
    </div>
  );
}
