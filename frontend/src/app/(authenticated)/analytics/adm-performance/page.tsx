"use client";

import React, { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { Table, type Column } from "@/components/ui/Table";
import { StatCard } from "@/components/ui/StatCard";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatPercent, formatNumber, cn } from "@/lib/utils";
import type { ADMRanking, ADMClassification } from "@/lib/types";
import { Trophy, AlertTriangle } from "lucide-react";

const CLASSIFICATION_BADGE: Record<ADMClassification, { variant: "success" | "warning" | "danger" | "default"; label: string }> = {
  HIGH_PERFORMER: { variant: "success", label: "High Performer" },
  AVERAGE: { variant: "warning", label: "Average" },
  STRUGGLING: { variant: "danger", label: "Struggling" },
  UNRESPONSIVE: { variant: "default", label: "Unresponsive" },
};

function ADMCard({ title, adms, icon }: { title: string; adms: ADMRanking[]; icon: React.ReactNode }) {
  return (
    <Card title={title}>
      <div className="mb-3 flex justify-center">{icon}</div>
      {adms.length === 0 ? (
        <p className="text-center text-sm text-gray-400">No data</p>
      ) : (
        <div className="space-y-3">
          {adms.map((adm, idx) => {
            const cls = CLASSIFICATION_BADGE[adm.classification] ?? CLASSIFICATION_BADGE.AVERAGE;
            return (
              <div key={adm.adm_id} className="flex items-center justify-between rounded-md border border-gray-100 p-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gray-100 text-xs font-bold text-gray-600">
                    {idx + 1}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{adm.name}</p>
                    <p className="text-xs text-gray-500">{adm.total_agents} agents</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-gray-900">
                    {formatPercent(adm.activation_rate)}
                  </p>
                  <Badge variant={cls.variant} className="text-[10px]">
                    {cls.label}
                  </Badge>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

export default function ADMPerformancePage() {
  const { data, isLoading, error } = useApi(() => api.analytics.admPerformance());
  const [sortKey, setSortKey] = useState("activation_rate");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  if (isLoading) return <LoadingSpinner text="Loading ADM performance..." />;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!data) return null;

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sorted = [...data.adm_rankings].sort((a, b) => {
    const aVal = (a as unknown as Record<string, number>)[sortKey] ?? 0;
    const bVal = (b as unknown as Record<string, number>)[sortKey] ?? 0;
    return sortDir === "asc" ? aVal - bVal : bVal - aVal;
  });

  const columns: Column<ADMRanking>[] = [
    {
      key: "name",
      header: "Name",
      sortable: true,
      render: (r) => <span className="font-medium text-gray-900">{r.name}</span>,
    },
    { key: "total_agents", header: "Total Agents", sortable: true },
    { key: "active_agents", header: "Active", sortable: true },
    {
      key: "activation_rate",
      header: "Activation Rate",
      sortable: true,
      render: (r) => (
        <div className="flex items-center gap-2">
          <div className="h-2 w-20 rounded-full bg-gray-200">
            <div
              className={cn(
                "h-2 rounded-full",
                r.activation_rate > 0.6 ? "bg-emerald-500" : r.activation_rate > 0.3 ? "bg-amber-400" : "bg-red-500"
              )}
              style={{ width: `${Math.min(r.activation_rate * 100, 100)}%` }}
            />
          </div>
          <span className="text-xs font-medium">{formatPercent(r.activation_rate)}</span>
        </div>
      ),
    },
    {
      key: "nudge_response_rate",
      header: "Nudge Response",
      sortable: true,
      render: (r) => formatPercent(r.nudge_response_rate),
    },
    {
      key: "reactivations_last_90d",
      header: "Reactivations (90d)",
      sortable: true,
      render: (r) => formatNumber(r.reactivations_last_90d),
    },
    {
      key: "classification",
      header: "Classification",
      sortable: true,
      render: (r) => {
        const cls = CLASSIFICATION_BADGE[r.classification] ?? CLASSIFICATION_BADGE.AVERAGE;
        return <Badge variant={cls.variant}>{cls.label}</Badge>;
      },
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">ADM Performance</h1>

      {/* Benchmark */}
      <StatCard
        label="Average Activation Rate (Benchmark)"
        value={formatPercent(data.average_activation_rate)}
        subtitle="Across all ADMs"
      />

      {/* Top 5 vs Bottom 5 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ADMCard
          title="Top 5 ADMs"
          adms={data.top_5_adms}
          icon={<Trophy className="h-8 w-8 text-amber-500" />}
        />
        <ADMCard
          title="Bottom 5 ADMs"
          adms={data.bottom_5_adms}
          icon={<AlertTriangle className="h-8 w-8 text-red-400" />}
        />
      </div>

      {/* Full Ranking Table */}
      <Card title="Full ADM Ranking" padding={false}>
        <Table
          columns={columns}
          data={sorted}
          keyExtractor={(r) => r.adm_id}
          sortKey={sortKey}
          sortDir={sortDir}
          onSort={handleSort}
        />
      </Card>
    </div>
  );
}
