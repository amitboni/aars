"use client";

import React, { useState, useCallback, useEffect } from "react";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { FilterBar, FilterSelect } from "@/components/ui/FilterBar";
import { Badge } from "@/components/ui/Badge";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatDate, cn } from "@/lib/utils";
import type { SettingsAuditLogEntry } from "@/lib/types";
import { ChevronDown } from "lucide-react";

const SECTION_OPTIONS = [
  { value: "lifecycle_thresholds", label: "Lifecycle Thresholds" },
  { value: "engagement_scoring_weights", label: "Engagement Weights" },
  { value: "contact_rules", label: "Contact Rules" },
  { value: "trai_calling_hours", label: "TRAI Calling Hours" },
  { value: "rate_limits", label: "Rate Limits" },
  { value: "branding", label: "Branding" },
  { value: "languages", label: "Languages" },
];

function formatValue(v: unknown): string {
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (v === null || v === undefined) return "—";
  return String(v);
}

export function SettingsAuditLog() {
  const [sectionFilter, setSectionFilter] = useState("");
  const [entries, setEntries] = useState<SettingsAuditLogEntry[]>([]);
  const [cursor, setCursor] = useState<string | undefined>();
  const [loadingMore, setLoadingMore] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading, error } = useApi(
    () =>
      api.settings.auditLog({
        section: sectionFilter || undefined,
        limit: 50,
      }),
    [sectionFilter]
  );

  useEffect(() => {
    if (data) {
      setEntries(data.data);
      setCursor(data.next_cursor ?? undefined);
    }
  }, [data]);

  const loadMore = useCallback(async () => {
    if (!cursor) return;
    setLoadingMore(true);
    try {
      const more = await api.settings.auditLog({
        section: sectionFilter || undefined,
        cursor,
        limit: 50,
      });
      setEntries((prev) => [...prev, ...more.data]);
      setCursor(more.next_cursor ?? undefined);
    } finally {
      setLoadingMore(false);
    }
  }, [cursor, sectionFilter]);

  if (isLoading) return <LoadingSpinner text="Loading audit log..." />;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  return (
    <div className="space-y-4">
      <FilterBar>
        <FilterSelect
          label="All Sections"
          value={sectionFilter}
          options={SECTION_OPTIONS}
          onChange={setSectionFilter}
        />
      </FilterBar>

      {entries.length === 0 ? (
        <EmptyState message="No audit log entries" />
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => {
            const expanded = expandedId === entry.id;
            return (
              <div
                key={entry.id}
                className="rounded-lg border border-gray-200 bg-white shadow-sm"
              >
                <button
                  onClick={() => setExpandedId(expanded ? null : entry.id)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant="info">
                      {entry.section.replace(/_/g, " ")}
                    </Badge>
                    <span className="text-sm text-gray-700">
                      {entry.changed_by_email}
                    </span>
                    <span className="text-xs text-gray-400">
                      {entry.changed_fields.length} field{entry.changed_fields.length !== 1 ? "s" : ""} changed
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">
                      {formatDate(entry.applied_at)}
                    </span>
                    <ChevronDown
                      className={cn(
                        "h-4 w-4 text-gray-400 transition-transform",
                        expanded && "rotate-180"
                      )}
                    />
                  </div>
                </button>
                {expanded && (
                  <div className="border-t border-gray-100 px-4 py-3">
                    <table className="min-w-full">
                      <thead>
                        <tr>
                          <th className="pb-2 text-left text-xs font-medium uppercase text-gray-500">
                            Field
                          </th>
                          <th className="pb-2 text-left text-xs font-medium uppercase text-gray-500">
                            Before
                          </th>
                          <th className="pb-2 text-left text-xs font-medium uppercase text-gray-500">
                            After
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {entry.changed_fields.map((field) => (
                          <tr key={field}>
                            <td className="py-1 pr-4 text-sm font-medium text-gray-700">
                              {field}
                            </td>
                            <td className="py-1 pr-4">
                              <span className="rounded bg-red-50 px-2 py-0.5 text-sm text-red-700">
                                {formatValue(entry.previous_values[field])}
                              </span>
                            </td>
                            <td className="py-1">
                              <span className="rounded bg-emerald-50 px-2 py-0.5 text-sm text-emerald-700">
                                {formatValue(entry.new_values[field])}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
          <Pagination
            hasMore={!!cursor}
            isLoading={loadingMore}
            onLoadMore={loadMore}
            count={entries.length}
          />
        </div>
      )}
    </div>
  );
}
