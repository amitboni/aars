"use client";

import React, { useState, useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Table, type Column } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar, FilterSelect, SearchInput } from "@/components/ui/FilterBar";
import { TableRowSkeleton } from "@/components/ui/Skeleton";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import {
  formatRelativeTime,
  maskPhone,
  engagementColor,
  engagementBgColor,
  cn,
} from "@/lib/utils";
import type { Agent } from "@/lib/types";
import { Eye } from "lucide-react";

const LIFECYCLE_OPTIONS: { value: string; label: string }[] = [
  { value: "onboarded", label: "Onboarded" },
  { value: "licensed", label: "Licensed" },
  { value: "first_sale", label: "First Sale" },
  { value: "active", label: "Active" },
  { value: "productive", label: "Productive" },
  { value: "at_risk", label: "At Risk" },
  { value: "dormant", label: "Dormant" },
  { value: "lapsed", label: "Lapsed" },
  { value: "terminated", label: "Terminated" },
];

export default function AgentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Initialize filters from URL query params
  const [lifecycleFilter, setLifecycleFilter] = useState(
    searchParams.get("lifecycle_state") ?? ""
  );
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [cursor, setCursor] = useState<string | undefined>();
  const [loadingMore, setLoadingMore] = useState(false);

  // Debounced search
  const [debouncedSearch, setDebouncedSearch] = useState(search);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading, error } = useApi(
    () =>
      api.agents.list({
        lifecycle_state: lifecycleFilter || undefined,
        search: debouncedSearch || undefined,
        limit: 50,
      }),
    [lifecycleFilter, debouncedSearch]
  );

  useEffect(() => {
    if (data) {
      setAgents(data.data);
      setCursor(data.next_cursor ?? undefined);
    }
  }, [data]);

  const loadMore = useCallback(async () => {
    if (!cursor) return;
    setLoadingMore(true);
    try {
      const more = await api.agents.list({
        lifecycle_state: lifecycleFilter || undefined,
        search: debouncedSearch || undefined,
        cursor,
        limit: 50,
      });
      setAgents((prev) => [...prev, ...more.data]);
      setCursor(more.next_cursor ?? undefined);
    } finally {
      setLoadingMore(false);
    }
  }, [cursor, lifecycleFilter, debouncedSearch]);

  const columns: Column<Agent>[] = [
    {
      key: "agent_code",
      header: "Code",
      render: (a) => (
        <span className="font-mono text-xs text-gray-700">{a.agent_code}</span>
      ),
    },
    {
      key: "full_name",
      header: "Name",
      render: (a) => (
        <span className="font-medium text-gray-900">{a.full_name}</span>
      ),
    },
    {
      key: "phone",
      header: "Phone",
      render: (a) => (
        <span className="font-mono text-xs text-gray-500">{maskPhone(a.phone)}</span>
      ),
    },
    {
      key: "lifecycle_state",
      header: "State",
      render: (a) => (
        <Badge variant="lifecycle" lifecycleState={a.lifecycle_state}>
          {a.lifecycle_state.replace(/_/g, " ")}
        </Badge>
      ),
    },
    {
      key: "engagement_score",
      header: "Engagement",
      render: (a) => {
        const score = a.engagement_score;
        return (
          <div className="flex items-center gap-2">
            <div className="h-2 w-16 rounded-full bg-gray-200">
              <div
                className={cn("h-2 rounded-full", engagementBgColor(score))}
                style={{ width: `${Math.min(score, 100)}%` }}
              />
            </div>
            <span className={cn("text-xs font-medium", engagementColor(score))}>
              {score.toFixed(0)}
            </span>
          </div>
        );
      },
    },
    {
      key: "last_contact_at",
      header: "Last Contact",
      render: (a) => (
        <span className="text-xs text-gray-500">
          {formatRelativeTime(a.last_contact_at)}
        </span>
      ),
    },
    {
      key: "assigned_adm_id",
      header: "ADM",
      render: (a) => (
        <span className="text-xs text-gray-500">
          {a.assigned_adm_id ? a.assigned_adm_id.slice(0, 8) + "..." : "—"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      className: "w-10",
      render: (a) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            router.push(`/agents/${a.id}`);
          }}
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-blue-600"
          title="View agent"
        >
          <Eye className="h-4 w-4" />
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Agents</h1>
        {agents.length > 0 && (
          <span className="text-sm text-gray-500">
            Showing {agents.length} agents
          </span>
        )}
      </div>

      {/* Filters */}
      <FilterBar>
        <FilterSelect
          label="All States"
          value={lifecycleFilter}
          options={LIFECYCLE_OPTIONS}
          onChange={setLifecycleFilter}
        />
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by name or code..."
          className="w-64"
        />
      </FilterBar>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {error ? (
          <div className="p-6 text-red-600">Failed to load agents: {error}</div>
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
                {Array.from({ length: 8 }).map((_, i) => (
                  <TableRowSkeleton key={i} cols={columns.length} />
                ))}
              </tbody>
            </table>
          </div>
        ) : agents.length === 0 ? (
          <EmptyState
            message={
              lifecycleFilter || debouncedSearch
                ? "No agents match your filters"
                : "No agents found"
            }
            actionLabel={
              lifecycleFilter || debouncedSearch ? "Clear filters" : undefined
            }
            onAction={
              lifecycleFilter || debouncedSearch
                ? () => {
                    setLifecycleFilter("");
                    setSearch("");
                  }
                : undefined
            }
          />
        ) : (
          <>
            <Table
              columns={columns}
              data={agents}
              keyExtractor={(a) => a.id}
              onRowClick={(a) => router.push(`/agents/${a.id}`)}
            />
            <Pagination
              hasMore={!!cursor}
              isLoading={loadingMore}
              onLoadMore={loadMore}
              count={agents.length}
            />
          </>
        )}
      </div>
    </div>
  );
}
