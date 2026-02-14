"use client";

import React from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { useAuth } from "@/hooks/useAuth";
import { Clock, Server, CheckCircle } from "lucide-react";

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between py-3 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  );
}

const LIFECYCLE_THRESHOLDS = [
  { state: "At Risk", description: "No positive signal for 30 days", color: "bg-amber-100 text-amber-800" },
  { state: "Dormant", description: "No positive signal for 90 days", color: "bg-red-100 text-red-800" },
  { state: "Lapsed", description: "No positive signal for 180 days", color: "bg-gray-100 text-gray-800" },
];

const ENGAGEMENT_RULES = [
  { rule: "Voice Call Weight", value: "+15 points" },
  { rule: "WhatsApp Reply Weight", value: "+10 points" },
  { rule: "Training Completion", value: "+20 points" },
  { rule: "Policy Sale", value: "+30 points" },
  { rule: "Decay Rate", value: "-2 points/week inactive" },
];

const INTEGRATIONS = [
  { name: "WhatsApp (Gupshup)", status: "connected" },
  { name: "Voice AI Provider", status: "connected" },
  { name: "PAS Integration", status: "mock" },
  { name: "LMS Integration", status: "mock" },
  { name: "Commission System", status: "mock" },
];

export default function SettingsPage() {
  const { user } = useAuth();

  if (!user) return <LoadingSpinner text="Loading settings..." />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {/* User Profile */}
      <Card title="User Profile">
        <div className="divide-y divide-gray-100">
          <InfoRow label="Name" value={user.full_name} />
          <InfoRow label="Email" value={user.email} />
          <InfoRow
            label="Roles"
            value={
              <div className="flex gap-2">
                {user.roles.map((r) => (
                  <Badge key={r} variant="info">
                    {r.replace(/_/g, " ")}
                  </Badge>
                ))}
              </div>
            }
          />
          <InfoRow
            label="Status"
            value={
              <Badge variant={user.is_active ? "success" : "danger"}>
                {user.is_active ? "Active" : "Inactive"}
              </Badge>
            }
          />
          <InfoRow
            label="Tenant ID"
            value={
              <span className="font-mono text-xs text-gray-600">
                {user.tenant_id}
              </span>
            }
          />
        </div>
      </Card>

      {/* Lifecycle Thresholds */}
      <Card title="Lifecycle Thresholds">
        <p className="mb-4 text-xs text-gray-500">
          Platform default thresholds for agent lifecycle state transitions (read-only)
        </p>
        <div className="space-y-2">
          {LIFECYCLE_THRESHOLDS.map((t) => (
            <div
              key={t.state}
              className="flex items-center justify-between rounded-md border border-gray-100 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${t.color}`}>
                  {t.state}
                </span>
                <span className="text-sm text-gray-600">{t.description}</span>
              </div>
              <Clock className="h-4 w-4 text-gray-300" />
            </div>
          ))}
        </div>
      </Card>

      {/* Engagement Scoring */}
      <Card title="Engagement Scoring Rules">
        <p className="mb-4 text-xs text-gray-500">
          Weights used to compute the agent engagement score (0-100) (read-only)
        </p>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Rule
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                  Value
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {ENGAGEMENT_RULES.map((r) => (
                <tr key={r.rule}>
                  <td className="px-4 py-3 text-sm text-gray-900">{r.rule}</td>
                  <td className="px-4 py-3 text-right text-sm font-mono text-gray-600">
                    {r.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Integration Status */}
      <Card title="Integration Status">
        <p className="mb-4 text-xs text-gray-500">
          External system connections and their current status
        </p>
        <div className="space-y-2">
          {INTEGRATIONS.map((i) => (
            <div
              key={i.name}
              className="flex items-center justify-between rounded-md border border-gray-100 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <Server className="h-4 w-4 text-gray-400" />
                <span className="text-sm font-medium text-gray-900">{i.name}</span>
              </div>
              <Badge
                variant={
                  i.status === "connected"
                    ? "success"
                    : i.status === "mock"
                    ? "warning"
                    : "danger"
                }
              >
                {i.status === "connected" ? "Connected" : i.status === "mock" ? "Mock" : "Disconnected"}
              </Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* TRAI Compliance */}
      <Card title="TRAI Compliance">
        <div className="divide-y divide-gray-100">
          <InfoRow label="Calling Hours" value="09:00 - 21:00 IST" />
          <InfoRow label="Applies To" value="Voice calls only (not WhatsApp)" />
          <InfoRow
            label="Status"
            value={
              <div className="flex items-center gap-1.5 text-emerald-600">
                <CheckCircle className="h-4 w-4" />
                <span className="text-sm font-medium">Enforced</span>
              </div>
            }
          />
        </div>
      </Card>
    </div>
  );
}
