"use client";

import React from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { StatCardSkeleton } from "@/components/ui/Skeleton";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatCurrency, formatPercent, formatNumber } from "@/lib/utils";
import { TrendingDown, GitBranch, Users, GraduationCap, DollarSign } from "lucide-react";

export default function AnalyticsPage() {
  const { data: roi, isLoading: roiLoading } = useApi(
    () => api.analytics.systemRoi(),
    []
  );
  const { data: training, isLoading: trainingLoading } = useApi(
    () => api.analytics.trainingEffectiveness(),
    []
  );

  const sections = [
    {
      title: "Dormancy Analysis",
      description: "Understand why agents become dormant and track trends over time",
      href: "/analytics/dormancy",
      icon: <TrendingDown className="h-6 w-6 text-red-500" />,
    },
    {
      title: "Reactivation Funnel",
      description: "Track conversion from contacted to sold across channels and playbooks",
      href: "/analytics/reactivation",
      icon: <GitBranch className="h-6 w-6 text-blue-500" />,
    },
    {
      title: "ADM Performance",
      description: "Compare ADM effectiveness, activation rates, and rankings",
      href: "/analytics/adm-performance",
      icon: <Users className="h-6 w-6 text-emerald-500" />,
    },
    {
      title: "Training Effectiveness",
      description: "Module completion rates, quiz scores, and training-to-sale correlation",
      href: "/analytics/training",
      icon: <GraduationCap className="h-6 w-6 text-purple-500" />,
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>

      {/* ROI Summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {roiLoading ? (
          Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)
        ) : roi ? (
          <>
            <StatCard
              label="New Premium (Reactivated)"
              value={formatCurrency(roi.new_premium_from_reactivated)}
              icon={<DollarSign className="h-5 w-5" />}
            />
            <StatCard
              label="System Cost"
              value={formatCurrency(roi.system_cost_this_month)}
              subtitle="This month"
            />
            <StatCard
              label="ROI Multiplier"
              value={`${roi.roi_multiplier.toFixed(1)}x`}
              trend={{
                direction: roi.roi_multiplier > 1 ? "up" : roi.roi_multiplier === 1 ? "stable" : "down",
                label: roi.roi_multiplier > 1 ? "Positive ROI" : "Break-even",
              }}
            />
            <StatCard
              label="Agents Reactivated"
              value={formatNumber(roi.agents_reactivated)}
              subtitle={`${formatCurrency(roi.average_premium_per_reactivation)} avg premium`}
            />
          </>
        ) : null}
      </div>

      {/* Training Quick Summary */}
      {!trainingLoading && training && (
        <Card title="Training Quick Summary">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg bg-gray-50 p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">
                {Object.keys(training.completion_rate_by_module).length}
              </p>
              <p className="text-xs text-gray-500">Training Modules</p>
            </div>
            <div className="rounded-lg bg-gray-50 p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">
                {Object.values(training.completion_rate_by_module).length > 0
                  ? formatPercent(
                      Object.values(training.completion_rate_by_module).reduce((a, b) => a + b, 0) /
                        Object.values(training.completion_rate_by_module).length
                    )
                  : "—"}
              </p>
              <p className="text-xs text-gray-500">Avg Completion Rate</p>
            </div>
            <div className="rounded-lg bg-gray-50 p-4 text-center">
              <p className="text-2xl font-bold text-amber-600">
                {training.top_drop_off_modules.length}
              </p>
              <p className="text-xs text-gray-500">Drop-off Modules</p>
            </div>
          </div>
        </Card>
      )}

      {/* Navigation Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {sections.map((s) => (
          <Link key={s.href} href={s.href}>
            <Card className="h-full transition-shadow hover:shadow-md">
              <div className="flex items-start gap-4">
                <div className="rounded-lg bg-gray-50 p-3">{s.icon}</div>
                <div>
                  <h3 className="font-semibold text-gray-900">{s.title}</h3>
                  <p className="mt-1 text-sm text-gray-500">{s.description}</p>
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
