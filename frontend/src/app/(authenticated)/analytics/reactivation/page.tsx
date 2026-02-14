"use client";

import React, { useState } from "react";
import { Card } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatNumber, formatPercent, cn } from "@/lib/utils";

const FUNNEL_COLORS = ["#3B82F6", "#8B5CF6", "#F59E0B", "#10B981"];

const PERIOD_OPTIONS = [
  { value: 30, label: "30 Days" },
  { value: 60, label: "60 Days" },
  { value: 90, label: "90 Days" },
];

function FunnelVisualization({
  stages,
}: {
  stages: { label: string; value: number; color: string; conversionRate?: number }[];
}) {
  const maxVal = Math.max(...stages.map((s) => s.value), 1);

  return (
    <div className="space-y-4">
      {stages.map((stage, idx) => {
        const pct = (stage.value / maxVal) * 100;
        return (
          <div key={stage.label}>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">{stage.label}</span>
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold text-gray-900">
                  {formatNumber(stage.value)}
                </span>
                {stage.conversionRate !== undefined && (
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                    {formatPercent(stage.conversionRate)} conv.
                  </span>
                )}
              </div>
            </div>
            <div className="h-9 w-full rounded-md bg-gray-100">
              <div
                className="flex h-9 items-center rounded-md px-3 text-sm font-semibold text-white transition-all"
                style={{
                  width: `${Math.max(pct, 5)}%`,
                  backgroundColor: stage.color,
                }}
              >
                {pct > 12 ? formatNumber(stage.value) : ""}
              </div>
            </div>
            {idx < stages.length - 1 && (
              <div className="ml-4 mt-1 flex items-center gap-1 text-xs text-gray-400">
                <span>&#8595;</span>
                {stages[idx + 1] && stage.value > 0 && (
                  <span>
                    {formatPercent(stages[idx + 1].value / stage.value)} pass through
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function BreakdownTable({
  title,
  breakdown,
}: {
  title: string;
  breakdown: Record<string, Record<string, number>>;
}) {
  const entries = Object.entries(breakdown);
  if (entries.length === 0) return null;

  const stageNames = ["contacted", "engaged", "trained", "sold"];

  return (
    <Card title={title}>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                {title.includes("Channel") ? "Channel" : "Playbook"}
              </th>
              {stageNames.map((s) => (
                <th key={s} className="px-3 py-3 text-right text-xs font-medium uppercase text-gray-500">
                  {s}
                </th>
              ))}
              <th className="px-3 py-3 text-right text-xs font-medium uppercase text-gray-500">
                Conv. Rate
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {entries.map(([name, stages]) => {
              const contacted = (stages as Record<string, number>)["contacted"] ?? 0;
              const sold = (stages as Record<string, number>)["sold"] ?? 0;
              const rate = contacted > 0 ? sold / contacted : 0;
              return (
                <tr key={name}>
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium capitalize text-gray-900">
                    {name.replace(/_/g, " ")}
                  </td>
                  {stageNames.map((s) => (
                    <td key={s} className="px-3 py-3 text-right text-sm text-gray-600">
                      {(stages as Record<string, number>)[s] ?? 0}
                    </td>
                  ))}
                  <td className="px-3 py-3 text-right text-sm">
                    <span className={cn(
                      "font-medium",
                      rate > 0.1 ? "text-emerald-600" : rate > 0 ? "text-amber-600" : "text-gray-400"
                    )}>
                      {formatPercent(rate)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function ReactivationPage() {
  const [period, setPeriod] = useState(90);
  const { data, isLoading, error } = useApi(
    () => api.analytics.reactivation(period),
    [period]
  );

  if (isLoading) return <LoadingSpinner text="Loading reactivation funnel..." />;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!data) return null;

  const convRates = data.conversion_rates;
  const stages = [
    { label: "Contacted", value: data.contacted, color: FUNNEL_COLORS[0] },
    {
      label: "Engaged",
      value: data.engaged,
      color: FUNNEL_COLORS[1],
      conversionRate: convRates["contacted_to_engaged"],
    },
    {
      label: "Trained",
      value: data.trained,
      color: FUNNEL_COLORS[2],
      conversionRate: convRates["engaged_to_trained"],
    },
    {
      label: "Sold",
      value: data.sold,
      color: FUNNEL_COLORS[3],
      conversionRate: convRates["trained_to_sold"],
    },
  ];

  const overallRate = data.contacted > 0 ? data.sold / data.contacted : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Reactivation Funnel</h1>

        {/* Period Selector */}
        <div className="flex rounded-lg border border-gray-200 bg-white">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setPeriod(opt.value)}
              className={cn(
                "px-4 py-2 text-sm font-medium transition-colors",
                period === opt.value
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-500 hover:text-gray-700",
                "first:rounded-l-lg last:rounded-r-lg"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Overall Rate */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        {stages.map((stage) => (
          <Card key={stage.label}>
            <p className="text-xs text-gray-500">{stage.label}</p>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {formatNumber(stage.value)}
            </p>
          </Card>
        ))}
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Funnel Stages</h3>
          <span className="text-sm text-gray-500">
            Overall: <strong className="text-gray-900">{formatPercent(overallRate)}</strong> conversion
          </span>
        </div>
        <FunnelVisualization stages={stages} />
      </Card>

      {/* Conversion Rate Cards */}
      <Card title="Stage Conversion Rates">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Object.entries(convRates).map(([label, rate]) => (
            <div key={label} className="rounded-lg bg-gray-50 p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">
                {formatPercent(rate)}
              </p>
              <p className="mt-1 text-xs capitalize text-gray-500">
                {label.replace(/_/g, " → ")}
              </p>
            </div>
          ))}
        </div>
      </Card>

      {/* Breakdowns */}
      <BreakdownTable title="By Channel" breakdown={data.by_channel} />
      <BreakdownTable title="By Playbook" breakdown={data.by_playbook} />
    </div>
  );
}
