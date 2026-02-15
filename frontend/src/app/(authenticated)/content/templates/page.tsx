"use client";

import React, { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Table, type Column } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar, FilterSelect } from "@/components/ui/FilterBar";
import { TableRowSkeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { TemplateSummary } from "@/lib/types";
import { Plus } from "lucide-react";

const CATEGORY_OPTIONS = [
  { value: "onboarding", label: "Onboarding" },
  { value: "reactivation", label: "Reactivation" },
  { value: "training", label: "Training" },
  { value: "nudge", label: "Nudge" },
  { value: "celebration", label: "Celebration" },
  { value: "reminder", label: "Reminder" },
];

const STATUS_OPTIONS = [
  { value: "draft", label: "Draft" },
  { value: "approved", label: "Approved" },
  { value: "active", label: "Active" },
  { value: "archived", label: "Archived" },
];

const STATUS_VARIANT: Record<string, "success" | "info" | "warning" | "danger" | "default"> = {
  draft: "default",
  approved: "info",
  active: "success",
  archived: "warning",
};

export default function TemplatesListPage() {
  const router = useRouter();
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [cursor, setCursor] = useState<string | undefined>();
  const [loadingMore, setLoadingMore] = useState(false);

  const { data, isLoading, error } = useApi(
    () =>
      api.templates.list({
        category: categoryFilter || undefined,
        status: statusFilter || undefined,
        limit: 50,
      }),
    [categoryFilter, statusFilter]
  );

  useEffect(() => {
    if (data) {
      setTemplates(data.data);
      setCursor(data.next_cursor ?? undefined);
    }
  }, [data]);

  const loadMore = useCallback(async () => {
    if (!cursor) return;
    setLoadingMore(true);
    try {
      const more = await api.templates.list({
        category: categoryFilter || undefined,
        status: statusFilter || undefined,
        cursor,
        limit: 50,
      });
      setTemplates((prev) => [...prev, ...more.data]);
      setCursor(more.next_cursor ?? undefined);
    } finally {
      setLoadingMore(false);
    }
  }, [cursor, categoryFilter, statusFilter]);

  const columns: Column<TemplateSummary>[] = [
    {
      key: "name",
      header: "Name",
      render: (t) => <span className="font-medium text-gray-900">{t.name}</span>,
    },
    {
      key: "category",
      header: "Category",
      render: (t) => <Badge variant="info">{t.category}</Badge>,
    },
    {
      key: "status",
      header: "Status",
      render: (t) => (
        <Badge variant={STATUS_VARIANT[t.status] ?? "default"}>
          {t.status}
        </Badge>
      ),
    },
    {
      key: "version",
      header: "Version",
      render: (t) => <span className="text-xs text-gray-500">v{t.version}</span>,
    },
    {
      key: "is_default",
      header: "Default",
      render: (t) =>
        t.is_default ? (
          <Badge variant="success">Yes</Badge>
        ) : (
          <span className="text-xs text-gray-400">No</span>
        ),
    },
    {
      key: "created_at",
      header: "Created",
      render: (t) => <span className="text-xs text-gray-500">{formatDate(t.created_at)}</span>,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Message Templates</h1>
        <Button onClick={() => router.push("/content/templates/new")}>
          <Plus className="mr-1.5 h-4 w-4" />
          Create Template
        </Button>
      </div>

      <FilterBar>
        <FilterSelect
          label="All Categories"
          value={categoryFilter}
          options={CATEGORY_OPTIONS}
          onChange={setCategoryFilter}
        />
        <FilterSelect
          label="All Statuses"
          value={statusFilter}
          options={STATUS_OPTIONS}
          onChange={setStatusFilter}
        />
      </FilterBar>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {error ? (
          <div className="p-6 text-red-600">Failed to load templates: {error}</div>
        ) : isLoading ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                    >
                      {col.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {Array.from({ length: 6 }).map((_, i) => (
                  <TableRowSkeleton key={i} cols={columns.length} />
                ))}
              </tbody>
            </table>
          </div>
        ) : templates.length === 0 ? (
          <EmptyState
            message={
              categoryFilter || statusFilter
                ? "No templates match your filters"
                : "No templates created yet"
            }
            actionLabel={
              categoryFilter || statusFilter ? "Clear filters" : undefined
            }
            onAction={
              categoryFilter || statusFilter
                ? () => {
                    setCategoryFilter("");
                    setStatusFilter("");
                  }
                : undefined
            }
          />
        ) : (
          <>
            <Table
              columns={columns}
              data={templates}
              keyExtractor={(t) => t.id}
              onRowClick={(t) => router.push(`/content/templates/${t.id}`)}
            />
            <Pagination
              hasMore={!!cursor}
              isLoading={loadingMore}
              onLoadMore={loadMore}
              count={templates.length}
            />
          </>
        )}
      </div>
    </div>
  );
}
