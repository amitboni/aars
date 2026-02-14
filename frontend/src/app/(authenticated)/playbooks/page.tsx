"use client";

import React, { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatPercent, formatNumber, formatDate, cn } from "@/lib/utils";
import {
  Phone,
  MessageCircle,
  GraduationCap,
  Bell,
  Play,
  Settings,
  X,
} from "lucide-react";

const ACTION_ICONS: Record<string, React.ReactNode> = {
  voice_call: <Phone className="h-4 w-4" />,
  whatsapp_message: <MessageCircle className="h-4 w-4" />,
  training_module: <GraduationCap className="h-4 w-4" />,
  nudge_adm: <Bell className="h-4 w-4" />,
  wait: <Settings className="h-4 w-4" />,
};

function PlaybookDetail({ playbookId, onClose }: { playbookId: string; onClose: () => void }) {
  const { data: playbook, isLoading } = useApi(
    () => api.playbooks.get(playbookId),
    [playbookId]
  );
  const { data: runsData } = useApi(
    () => api.playbooks.runs({ limit: 10 }),
    []
  );

  // Filter runs for this playbook client-side
  const runs = runsData?.data.filter((r) => r.playbook_id === playbookId) ?? [];

  if (isLoading) return <LoadingSpinner text="Loading playbook..." />;
  if (!playbook) return null;

  const STATUS_VARIANT: Record<string, "success" | "info" | "warning" | "danger" | "default"> = {
    completed: "success",
    running: "info",
    pending: "default",
    failed: "danger",
    expired: "warning",
    cancelled: "warning",
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white shadow-xl">
        <div className="sticky top-0 flex items-center justify-between border-b bg-white px-6 py-4">
          <div>
            <h2 className="text-lg font-bold text-gray-900">{playbook.name}</h2>
            {playbook.description && (
              <p className="mt-0.5 text-sm text-gray-500">{playbook.description}</p>
            )}
          </div>
          <button onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-6 p-6">
          {/* Stats */}
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg bg-gray-50 p-3">
              <p className="text-lg font-bold">{playbook.steps.length}</p>
              <p className="text-xs text-gray-500">Steps</p>
            </div>
            <div className="rounded-lg bg-gray-50 p-3">
              <p className="text-lg font-bold">{formatNumber(playbook.times_executed)}</p>
              <p className="text-xs text-gray-500">Executed</p>
            </div>
            <div className="rounded-lg bg-gray-50 p-3">
              <p className="text-lg font-bold">{formatPercent(playbook.success_rate)}</p>
              <p className="text-xs text-gray-500">Success Rate</p>
            </div>
          </div>

          {/* Steps */}
          <div>
            <h3 className="mb-3 text-sm font-semibold text-gray-900">Steps</h3>
            <div className="space-y-2">
              {playbook.steps
                .sort((a, b) => a.step_number - b.step_number)
                .map((step) => (
                  <div
                    key={step.id}
                    className="flex items-center gap-3 rounded-md border border-gray-100 p-3"
                  >
                    <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-blue-50 text-xs font-bold text-blue-600">
                      {step.step_number}
                    </span>
                    <span className="text-gray-400">
                      {ACTION_ICONS[step.action_type] ?? <Play className="h-4 w-4" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900">{step.name}</p>
                      <p className="text-xs text-gray-500">
                        {step.action_type.replace(/_/g, " ")}
                        {step.delay_days > 0 && (
                          <span className="ml-2 text-gray-400">
                            +{step.delay_days}d delay
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                ))}
            </div>
          </div>

          {/* Recent Runs */}
          {runs.length > 0 && (
            <div>
              <h3 className="mb-3 text-sm font-semibold text-gray-900">
                Recent Runs ({runs.length})
              </h3>
              <div className="space-y-2">
                {runs.map((run) => (
                  <div key={run.id} className="flex items-center justify-between rounded-md border border-gray-100 p-3">
                    <div>
                      <Badge variant={STATUS_VARIANT[run.status] ?? "default"}>
                        {run.status}
                      </Badge>
                      <span className="ml-2 text-xs text-gray-500">
                        Step {run.current_step_number} / {run.steps_executed} executed
                      </span>
                    </div>
                    <span className="text-xs text-gray-400">
                      {formatDate(run.started_at)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function PlaybooksPage() {
  const { data, isLoading, error } = useApi(() => api.playbooks.list({ limit: 50 }));
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (isLoading) return <LoadingSpinner text="Loading playbooks..." />;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!data || data.data.length === 0)
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Playbooks</h1>
        <EmptyState message="No playbooks configured" />
      </div>
    );

  const activeCount = data.data.filter((pb) => pb.is_active).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Playbooks</h1>
        <span className="text-sm text-gray-500">
          {activeCount} active / {data.data.length} total
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {data.data.map((pb) => (
          <button
            key={pb.id}
            onClick={() => setSelectedId(pb.id)}
            className="text-left"
          >
            <Card className="h-full transition-shadow hover:shadow-md">
              <div className="flex items-start justify-between">
                <h3 className="font-semibold text-gray-900">{pb.name}</h3>
                <Badge variant={pb.is_active ? "success" : "default"}>
                  {pb.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
              {pb.description && (
                <p className="mt-2 text-sm text-gray-500 line-clamp-2">
                  {pb.description}
                </p>
              )}
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-lg font-bold text-gray-900">{pb.steps_count}</p>
                  <p className="text-xs text-gray-500">Steps</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-gray-900">
                    {formatNumber(pb.times_executed)}
                  </p>
                  <p className="text-xs text-gray-500">Executed</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-gray-900">
                    {formatPercent(pb.success_rate)}
                  </p>
                  <p className="text-xs text-gray-500">Success</p>
                </div>
              </div>
              {/* Success rate bar */}
              <div className="mt-3 h-1.5 w-full rounded-full bg-gray-100">
                <div
                  className={cn(
                    "h-1.5 rounded-full",
                    pb.success_rate > 0.6 ? "bg-emerald-500" : pb.success_rate > 0.3 ? "bg-amber-400" : "bg-red-400"
                  )}
                  style={{ width: `${Math.min(pb.success_rate * 100, 100)}%` }}
                />
              </div>
            </Card>
          </button>
        ))}
      </div>

      {/* Detail Modal */}
      {selectedId && (
        <PlaybookDetail
          playbookId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
