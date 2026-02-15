"use client";

import React from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import type { SettingsSection, SettingFieldMetadata } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SettingsSectionCardProps {
  sectionName: string;
  section: SettingsSection;
  isEditing: boolean;
  editValues: Record<string, unknown>;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onChange: (key: string, value: unknown) => void;
  onReviewChanges: () => void;
  saving: boolean;
}

function formatSectionName(name: string): string {
  return name
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function renderInput(
  key: string,
  value: unknown,
  meta: SettingFieldMetadata,
  onChange: (key: string, value: unknown) => void
) {
  if (meta.allowed_values && meta.allowed_values.length > 0) {
    return (
      <select
        value={String(value)}
        onChange={(e) => onChange(key, e.target.value)}
        className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        {meta.allowed_values.map((v) => (
          <option key={v} value={v}>{v}</option>
        ))}
      </select>
    );
  }

  if (meta.type === "int" || meta.type === "float") {
    return (
      <input
        type="number"
        value={value as number}
        min={meta.min}
        max={meta.max}
        step={meta.type === "float" ? 0.01 : 1}
        onChange={(e) =>
          onChange(key, meta.type === "float" ? parseFloat(e.target.value) : parseInt(e.target.value, 10))
        }
        className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
    );
  }

  if (meta.type === "bool") {
    return (
      <label className="inline-flex items-center gap-2">
        <input
          type="checkbox"
          checked={!!value}
          onChange={(e) => onChange(key, e.target.checked)}
          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm text-gray-700">{value ? "Enabled" : "Disabled"}</span>
      </label>
    );
  }

  if (meta.type === "list") {
    return (
      <input
        type="text"
        value={Array.isArray(value) ? (value as string[]).join(", ") : String(value)}
        onChange={(e) =>
          onChange(
            key,
            e.target.value
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          )
        }
        className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        placeholder="Comma-separated values"
      />
    );
  }

  return (
    <input
      type="text"
      value={String(value ?? "")}
      onChange={(e) => onChange(key, e.target.value)}
      className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
    />
  );
}

export function SettingsSectionCard({
  sectionName,
  section,
  isEditing,
  editValues,
  onStartEdit,
  onCancelEdit,
  onChange,
  onReviewChanges,
  saving,
}: SettingsSectionCardProps) {
  const values = isEditing ? editValues : section.values;
  const metadata = section.metadata ?? {};
  const keys = Object.keys(section.values);

  // Check if engagement weights to show total
  const isEngagement = sectionName === "engagement_scoring_weights";
  let totalWeight = 0;
  if (isEngagement && isEditing) {
    totalWeight = Object.values(editValues).reduce((sum: number, v) => sum + (typeof v === "number" ? v : 0), 0);
  }

  // Group rate_limits by prefix
  const isRateLimits = sectionName === "rate_limits";
  const groupedKeys: Record<string, string[]> = {};
  if (isRateLimits) {
    keys.forEach((k) => {
      const prefix = k.includes(".") ? k.split(".")[0] : "general";
      if (!groupedKeys[prefix]) groupedKeys[prefix] = [];
      groupedKeys[prefix].push(k);
    });
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900">
          {formatSectionName(sectionName)}
        </h3>
        {!isEditing ? (
          <Button variant="secondary" size="sm" onClick={onStartEdit}>
            Edit
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={onCancelEdit} disabled={saving}>
              Cancel
            </Button>
            <Button size="sm" onClick={onReviewChanges} loading={saving}>
              Review Changes
            </Button>
          </div>
        )}
      </div>

      {isEngagement && isEditing && (
        <div
          className={cn(
            "mb-3 rounded-md px-3 py-2 text-sm font-medium",
            Math.abs(totalWeight - 100) < 0.01
              ? "bg-emerald-50 text-emerald-700"
              : "bg-amber-50 text-amber-700"
          )}
        >
          Total weight: {totalWeight.toFixed(1)}
          {Math.abs(totalWeight - 100) >= 0.01 && " (should equal 100)"}
        </div>
      )}

      {isRateLimits ? (
        Object.entries(groupedKeys).map(([prefix, groupKeys]) => (
          <div key={prefix} className="mb-4">
            <p className="mb-2 text-xs font-medium uppercase text-gray-400">
              {prefix}
            </p>
            <div className="space-y-2">
              {groupKeys.map((key) => {
                const meta = (metadata[key] ?? { type: "str", description: key }) as SettingFieldMetadata;
                return (
                  <div
                    key={key}
                    className="flex items-center justify-between rounded-md border border-gray-100 px-4 py-2.5"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-700">{meta.description}</p>
                      {meta.min !== undefined && meta.max !== undefined && (
                        <p className="text-xs text-gray-400">
                          Range: {meta.min} – {meta.max}
                        </p>
                      )}
                    </div>
                    <div className="ml-4 w-40">
                      {isEditing
                        ? renderInput(key, values[key], meta, onChange)
                        : <span className="text-sm font-medium text-gray-900">
                            {Array.isArray(values[key])
                              ? (values[key] as string[]).join(", ")
                              : String(values[key])}
                          </span>
                      }
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))
      ) : (
        <div className="space-y-2">
          {keys.map((key) => {
            const meta = (metadata[key] ?? { type: "str", description: key }) as SettingFieldMetadata;
            return (
              <div
                key={key}
                className="flex items-center justify-between rounded-md border border-gray-100 px-4 py-2.5"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700">{meta.description}</p>
                  {meta.min !== undefined && meta.max !== undefined && (
                    <p className="text-xs text-gray-400">
                      Range: {meta.min} – {meta.max}
                    </p>
                  )}
                </div>
                <div className="ml-4 w-40">
                  {isEditing
                    ? renderInput(key, values[key], meta, onChange)
                    : <span className="text-sm font-medium text-gray-900">
                        {typeof values[key] === "boolean"
                          ? (values[key] ? "Yes" : "No")
                          : Array.isArray(values[key])
                          ? (values[key] as string[]).join(", ")
                          : String(values[key])}
                      </span>
                  }
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
