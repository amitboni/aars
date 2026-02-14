"use client";

import React from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatPercent, cn } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { AlertTriangle } from "lucide-react";

export default function TrainingPage() {
  const { data, isLoading, error } = useApi(() => api.analytics.trainingEffectiveness());

  if (isLoading) return <LoadingSpinner text="Loading training analytics..." />;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!data) return null;

  const completionData = Object.entries(data.completion_rate_by_module).map(
    ([module, rate]) => ({
      module: module.length > 20 ? module.slice(0, 20) + "..." : module,
      fullName: module,
      rate: rate * 100,
    })
  );

  const correlationData = Object.entries(data.training_to_sale_correlation).map(
    ([module, corr]) => ({
      module: module.length > 20 ? module.slice(0, 20) + "..." : module,
      fullName: module,
      correlation: corr * 100,
    })
  );

  const scoreEntries = Object.entries(data.average_scores_by_module);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Training Effectiveness</h1>

      {/* Drop-off Modules Alert */}
      {data.top_drop_off_modules.length > 0 && (
        <Card>
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-500" />
            <div>
              <h3 className="text-sm font-semibold text-gray-900">
                High Drop-off Modules
              </h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {data.top_drop_off_modules.map((m) => (
                  <Badge key={m} variant="warning">{m}</Badge>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Completion Rates */}
      <Card title="Module Completion Rates">
        {completionData.length === 0 ? (
          <EmptyState message="No completion data available" />
        ) : (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={completionData}
                layout="vertical"
                margin={{ left: 120, right: 20 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                <YAxis dataKey="module" type="category" tick={{ fontSize: 11 }} width={115} />
                <Tooltip
                  formatter={(value) => [`${(value as number).toFixed(1)}%`, "Completion Rate"]}
                  labelFormatter={(label) => {
                    const item = completionData.find((d) => d.module === label);
                    return item?.fullName ?? label;
                  }}
                />
                <Bar dataKey="rate" fill="#3B82F6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* Training-to-Sale Correlation */}
      <Card title="Training-to-Sale Correlation">
        {correlationData.length === 0 ? (
          <EmptyState message="No correlation data available" />
        ) : (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={correlationData}
                layout="vertical"
                margin={{ left: 120, right: 20 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tickFormatter={(v) => `${v}%`} />
                <YAxis dataKey="module" type="category" tick={{ fontSize: 11 }} width={115} />
                <Tooltip
                  formatter={(value) => [`${(value as number).toFixed(1)}%`, "Correlation"]}
                  labelFormatter={(label) => {
                    const item = correlationData.find((d) => d.module === label);
                    return item?.fullName ?? label;
                  }}
                />
                <Bar dataKey="correlation" fill="#10B981" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* Average Scores Table */}
      <Card title="Average Quiz Scores by Module">
        {scoreEntries.length === 0 ? (
          <EmptyState message="No quiz score data" />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                    Module
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                    Avg Score
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {scoreEntries.map(([module, score]) => {
                  const isDropoff = data.top_drop_off_modules.includes(module);
                  return (
                    <tr key={module}>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {module}
                        {isDropoff && (
                          <AlertTriangle className="ml-2 inline h-3.5 w-3.5 text-amber-500" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-sm">
                        <span className={cn(
                          "font-medium",
                          score >= 0.7 ? "text-emerald-600" : score >= 0.5 ? "text-amber-600" : "text-red-600"
                        )}>
                          {formatPercent(score)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Badge variant={score >= 0.7 ? "success" : score >= 0.5 ? "warning" : "danger"}>
                          {score >= 0.7 ? "Good" : score >= 0.5 ? "Fair" : "Low"}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
