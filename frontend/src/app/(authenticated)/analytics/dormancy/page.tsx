"use client";

import React from "react";
import { Card } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { StatCard } from "@/components/ui/StatCard";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
// Icons removed — trends shown via color-coded bars

// Map dormancy reason prefixes to category colors
function reasonCategoryColor(reason: string): string {
  const r = reason.toLowerCase();
  if (r.includes("training") || r.includes("knowledge") || r.includes("skill"))
    return "#3B82F6"; // blue - TRAINING_GAP
  if (r.includes("engagement") || r.includes("motivation") || r.includes("contact"))
    return "#F97316"; // orange - ENGAGEMENT_GAP
  if (r.includes("economic") || r.includes("commission") || r.includes("income") || r.includes("financial"))
    return "#EF4444"; // red - ECONOMIC
  if (r.includes("operational") || r.includes("system") || r.includes("infrastructure"))
    return "#EAB308"; // yellow - OPERATIONAL
  if (r.includes("personal") || r.includes("health") || r.includes("family"))
    return "#6B7280"; // gray - PERSONAL
  if (r.includes("regulatory") || r.includes("license") || r.includes("compliance"))
    return "#8B5CF6"; // purple - REGULATORY
  return "#6B7280";
}

export default function DormancyPage() {
  const { data, isLoading, error } = useApi(() => api.analytics.dormancy());

  if (isLoading) return <LoadingSpinner text="Loading dormancy analytics..." />;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!data) return null;

  const reasonData = Object.entries(data.reason_distribution)
    .map(([name, value]) => ({
      name: name.replace(/_/g, " "),
      rawName: name,
      value,
      fill: reasonCategoryColor(name),
    }))
    .sort((a, b) => b.value - a.value);

  const trendData = Object.entries(data.trend_vs_last_month)
    .map(([reason, change]) => ({
      reason: reason.replace(/_/g, " "),
      change,
      fill: change > 0 ? "#EF4444" : "#10B981",
    }))
    .sort((a, b) => Math.abs(b.change) - Math.abs(a.change));

  const totalDormant = reasonData.reduce((sum, r) => sum + r.value, 0);
  const regionEntries = Object.entries(data.regional_breakdown);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dormancy Analytics</h1>

      {/* Highlights */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Total Dormant"
          value={formatNumber(totalDormant)}
          subtitle="Across all reasons"
        />
        <StatCard
          label="Top Growing Reason"
          value={data.top_growing_reason?.replace(/_/g, " ") ?? "None"}
          trend={data.top_growing_reason ? { direction: "up", label: "Increasing" } : undefined}
        />
        <StatCard
          label="Top Shrinking Reason"
          value={data.top_shrinking_reason?.replace(/_/g, " ") ?? "None"}
          trend={data.top_shrinking_reason ? { direction: "down", label: "Decreasing" } : undefined}
        />
      </div>

      {/* Category Legend */}
      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <span className="text-xs font-medium text-gray-500">Categories:</span>
          {[
            { label: "Training Gap", color: "#3B82F6" },
            { label: "Engagement Gap", color: "#F97316" },
            { label: "Economic", color: "#EF4444" },
            { label: "Operational", color: "#EAB308" },
            { label: "Personal", color: "#6B7280" },
            { label: "Regulatory", color: "#8B5CF6" },
          ].map((c) => (
            <div key={c.label} className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded" style={{ backgroundColor: c.color }} />
              <span className="text-xs text-gray-600">{c.label}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Reason Distribution - Horizontal Bar */}
      <Card title="Reason Distribution">
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={reasonData} layout="vertical" margin={{ left: 140, right: 30 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis
                dataKey="name"
                type="category"
                tick={{ fontSize: 11 }}
                width={135}
              />
              <Tooltip
                formatter={(value) => [formatNumber(value as number), "Agents"]}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {reasonData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Trend vs Last Month */}
      <Card title="Trend vs Last Month">
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={trendData} layout="vertical" margin={{ left: 140, right: 30 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis dataKey="reason" type="category" tick={{ fontSize: 11 }} width={135} />
              <Tooltip
                formatter={(value) => {
                  const v = value as number;
                  return [
                    `${v > 0 ? "+" : ""}${formatNumber(v)}`,
                    "Change",
                  ];
                }}
              />
              <Bar dataKey="change" radius={[0, 4, 4, 0]}>
                {trendData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Regional Breakdown */}
      {regionEntries.length > 0 && (
        <Card title="Regional Breakdown">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                    Region
                  </th>
                  {reasonData.slice(0, 5).map((r) => (
                    <th key={r.rawName} className="px-3 py-3 text-right text-xs font-medium uppercase text-gray-500">
                      {r.name.length > 15 ? r.name.slice(0, 15) + "..." : r.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {regionEntries.map(([region, reasons]) => (
                  <tr key={region}>
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                      {region.slice(0, 8)}...
                    </td>
                    {reasonData.slice(0, 5).map((r) => (
                      <td key={r.rawName} className="px-3 py-3 text-right text-sm text-gray-600">
                        {(reasons as Record<string, number>)[r.rawName] ?? 0}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Ranked Table */}
      <Card title="All Reasons Ranked">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">#</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Reason</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Count</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Trend</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {reasonData.map((item, idx) => {
                const trend = data.trend_vs_last_month[item.rawName] ?? 0;
                return (
                  <tr key={item.rawName}>
                    <td className="px-4 py-3 text-sm text-gray-500">{idx + 1}</td>
                    <td className="px-4 py-3 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="inline-block h-3 w-3 rounded" style={{ backgroundColor: item.fill }} />
                        <span className="font-medium capitalize text-gray-900">{item.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-sm font-medium text-gray-900">
                      {formatNumber(item.value)}
                    </td>
                    <td className="px-4 py-3 text-right text-sm">
                      {trend !== 0 && (
                        <span className={trend > 0 ? "text-red-600" : "text-emerald-600"}>
                          {trend > 0 ? "+" : ""}{trend}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
