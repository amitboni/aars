"use client";

import React, { useEffect, useRef, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { SignalIcon, getSignalCategory } from "@/components/ui/SignalIcon";
import { StatCardSkeleton, ChartSkeleton } from "@/components/ui/Skeleton";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatNumber, formatPercent, formatRelativeTime } from "@/lib/utils";
import type { DashboardData, DormancyAnalytics, ReactivationFunnel, Signal } from "@/lib/types";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from "recharts";
import { Users, AlertTriangle, Moon, RefreshCw } from "lucide-react";

const LIFECYCLE_CHART_COLORS: Record<string, string> = {
  onboarded: "#6B7280",
  licensed: "#3B82F6",
  first_sale: "#8B5CF6",
  active: "#10B981",
  productive: "#059669",
  at_risk: "#F59E0B",
  dormant: "#EF4444",
  lapsed: "#9CA3AF",
  terminated: "#374151",
};

const PIE_COLORS = [
  "#EF4444", "#F59E0B", "#3B82F6", "#8B5CF6", "#10B981",
];

const FUNNEL_COLORS = ["#3B82F6", "#8B5CF6", "#F59E0B", "#10B981"];

const NOTABLE_SIGNALS = [
  "policy_sold",
  "lifecycle_state_changed",
  "playbook_completed",
  "escalation_created",
  "license_status_changed",
  "training_completed_external",
  "voice_call_outcome",
  "whatsapp_agent_replied",
  "adm_nudge_acted_on",
  "commission_credited",
];

// --- Dashboard sub-sections ---

function DashboardStatCards({
  data,
  router,
}: {
  data: DashboardData;
  router: ReturnType<typeof useRouter>;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="Total Agents"
        value={formatNumber(data.total_agents)}
        icon={<Users className="h-5 w-5" />}
        subtitle={`${formatNumber(data.active_agents)} active`}
      />
      <StatCard
        label="Activation Rate"
        value={formatPercent(data.agent_activation_rate)}
        trend={{
          direction: data.agent_activation_trend,
          label: data.agent_activation_trend === "up" ? "vs last month" : data.agent_activation_trend === "down" ? "vs last month" : "stable",
        }}
      />
      <StatCard
        label="At-Risk Agents"
        value={formatNumber(data.at_risk_agents)}
        icon={<AlertTriangle className="h-5 w-5" />}
        onClick={() => router.push("/agents?lifecycle_state=at_risk")}
      />
      <StatCard
        label="Reactivations This Month"
        value={formatNumber(data.reactivation_count_this_month)}
        icon={<Moon className="h-5 w-5" />}
      />
    </div>
  );
}

function LifecycleDistributionChart({
  data,
  onStateClick,
}: {
  data: DashboardData;
  onStateClick: (state: string) => void;
}) {
  const chartData = Object.entries(data.agents_by_state).map(([state, count]) => ({
    state: state.replace(/_/g, " "),
    rawState: state,
    count,
    fill: LIFECYCLE_CHART_COLORS[state] ?? "#6B7280",
  }));

  return (
    <Card title="Agent Lifecycle Distribution">
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ left: 90, right: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 12 }} />
            <YAxis
              dataKey="state"
              type="category"
              tick={{ fontSize: 12 }}
              width={85}
            />
            <Tooltip
              formatter={(value) => [formatNumber(value as number), "Agents"]}
            />
            <Bar
              dataKey="count"
              radius={[0, 4, 4, 0]}
              cursor="pointer"
              onClick={(_entry, index) => {
                if (index !== undefined && chartData[index]) {
                  onStateClick(chartData[index].rawState);
                }
              }}
            >
              {chartData.map((entry, idx) => (
                <Cell key={idx} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function DormancyPanel({ data }: { data: DormancyAnalytics | null }) {
  if (!data) return <ChartSkeleton height="h-48" />;

  const reasonData = Object.entries(data.reason_distribution)
    .map(([name, value]) => ({ name: name.replace(/_/g, " "), value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 5);

  return (
    <Card title="Top Dormancy Reasons">
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={reasonData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={45}
              outerRadius={80}
              paddingAngle={2}
            >
              {reasonData.map((_, idx) => (
                <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => [formatNumber(value as number), "Agents"]} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 space-y-1.5">
        {reasonData.map((item, idx) => (
          <div key={item.name} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }}
              />
              <span className="capitalize text-gray-600">{item.name}</span>
            </div>
            <span className="font-medium text-gray-900">{formatNumber(item.value)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ReactivationPanel({ data }: { data: ReactivationFunnel | null }) {
  if (!data) return <ChartSkeleton height="h-48" />;

  const stages = [
    { label: "Contacted", value: data.contacted },
    { label: "Engaged", value: data.engaged },
    { label: "Trained", value: data.trained },
    { label: "Sold", value: data.sold },
  ];
  const maxVal = Math.max(...stages.map((s) => s.value), 1);

  return (
    <Card title="Reactivation Funnel">
      <div className="space-y-3">
        {stages.map((stage, idx) => {
          const pct = (stage.value / maxVal) * 100;
          const convKey = Object.keys(data.conversion_rates)[idx];
          const rate = convKey ? data.conversion_rates[convKey] : undefined;

          return (
            <div key={stage.label}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="font-medium text-gray-700">{stage.label}</span>
                <span className="text-gray-500">
                  {formatNumber(stage.value)}
                  {rate !== undefined && (
                    <span className="ml-1 text-gray-400">
                      ({formatPercent(rate)})
                    </span>
                  )}
                </span>
              </div>
              <div className="h-7 w-full rounded bg-gray-100">
                <div
                  className="flex h-7 items-center rounded px-2 text-xs font-medium text-white transition-all"
                  style={{
                    width: `${Math.max(pct, 6)}%`,
                    backgroundColor: FUNNEL_COLORS[idx],
                  }}
                >
                  {pct > 15 ? formatNumber(stage.value) : ""}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function RecentActivityFeed({ signals }: { signals: Signal[] | null }) {
  if (!signals) {
    return (
      <Card title="Recent Activity">
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex gap-3">
              <div className="h-8 w-8 animate-pulse rounded-full bg-gray-200" />
              <div className="flex-1 space-y-1.5">
                <div className="h-3 w-3/4 animate-pulse rounded bg-gray-200" />
                <div className="h-3 w-1/2 animate-pulse rounded bg-gray-200" />
              </div>
            </div>
          ))}
        </div>
      </Card>
    );
  }

  if (signals.length === 0) {
    return (
      <Card title="Recent Activity">
        <p className="py-8 text-center text-sm text-gray-400">No recent activity</p>
      </Card>
    );
  }

  return (
    <Card title="Recent Activity">
      <div className="space-y-3">
        {signals.map((s) => (
          <div key={s.id} className="flex items-start gap-3">
            <SignalIcon signalType={s.signal_type} size="md" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900">
                  {s.signal_type.replace(/_/g, " ")}
                </span>
                <Badge variant="default" className="text-[10px]">
                  {getSignalCategory(s.signal_type)}
                </Badge>
              </div>
              <p className="text-xs text-gray-500">
                Agent: {s.agent_id ? s.agent_id.slice(0, 8) + "..." : "—"}
                {s.channel && <> &middot; {s.channel.replace(/_/g, " ")}</>}
              </p>
            </div>
            <span className="flex-shrink-0 text-xs text-gray-400">
              {formatRelativeTime(s.timestamp)}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// --- Main Dashboard ---

export default function DashboardPage() {
  const router = useRouter();
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const {
    data: dashboardData,
    isLoading: dashLoading,
    error: dashError,
    refetch: refetchDash,
  } = useApi(() => api.analytics.dashboard(), []);

  const { data: dormancyData, refetch: refetchDormancy } = useApi(
    () => api.analytics.dormancy(),
    []
  );

  const { data: reactivationData, refetch: refetchReactivation } = useApi(
    () => api.analytics.reactivation(),
    []
  );

  const [recentSignals, setRecentSignals] = useState<Signal[] | null>(null);

  const fetchRecentSignals = useCallback(async () => {
    try {
      const res = await api.signals.list({
        limit: 10,
        signal_type: NOTABLE_SIGNALS.join(","),
      });
      setRecentSignals(res.data);
    } catch {
      // If filtering by signal_type isn't supported with comma separation,
      // fall back to fetching without filter
      try {
        const res = await api.signals.list({ limit: 10 });
        setRecentSignals(
          res.data.filter((s) => NOTABLE_SIGNALS.includes(s.signal_type))
        );
      } catch {
        setRecentSignals([]);
      }
    }
  }, []);

  useEffect(() => {
    fetchRecentSignals();
  }, [fetchRecentSignals]);

  // Auto-refresh every 60s
  const refetchAll = useCallback(() => {
    refetchDash();
    refetchDormancy();
    refetchReactivation();
    fetchRecentSignals();
    setLastRefresh(new Date());
  }, [refetchDash, refetchDormancy, refetchReactivation, fetchRecentSignals]);

  useEffect(() => {
    refreshTimerRef.current = setInterval(refetchAll, 60_000);
    return () => {
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
  }, [refetchAll]);

  const handleStateClick = (state: string) => {
    router.push(`/agents?lifecycle_state=${state}`);
  };

  if (dashError) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-red-600">Failed to load dashboard: {dashError}</p>
        <button
          onClick={refetchAll}
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <button
          onClick={refetchAll}
          className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          title="Refresh"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Updated {formatRelativeTime(lastRefresh.toISOString())}
        </button>
      </div>

      {/* Row 1: Stat Cards */}
      {dashLoading || !dashboardData ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <StatCardSkeleton key={i} />
          ))}
        </div>
      ) : (
        <DashboardStatCards data={dashboardData} router={router} />
      )}

      {/* Row 2: Lifecycle Distribution */}
      {dashLoading || !dashboardData ? (
        <ChartSkeleton height="h-72" />
      ) : (
        <LifecycleDistributionChart
          data={dashboardData}
          onStateClick={handleStateClick}
        />
      )}

      {/* Row 3: Dormancy + Reactivation side by side */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DormancyPanel data={dormancyData} />
        <ReactivationPanel data={reactivationData} />
      </div>

      {/* Row 4: Recent Activity */}
      <RecentActivityFeed signals={recentSignals} />
    </div>
  );
}
