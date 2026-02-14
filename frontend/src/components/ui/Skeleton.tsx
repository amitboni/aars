import React from "react";
import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div className={cn("animate-pulse rounded bg-gray-200", className)} />
  );
}

export function StatCardSkeleton() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="mt-2 h-8 w-20" />
      <Skeleton className="mt-3 h-4 w-16" />
    </div>
  );
}

export function ChartSkeleton({ height = "h-64" }: { height?: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <Skeleton className="mb-4 h-4 w-40" />
      <Skeleton className={cn("w-full rounded", height)} />
    </div>
  );
}

export function TableRowSkeleton({ cols = 6 }: { cols?: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4 w-3/4" />
        </td>
      ))}
    </tr>
  );
}
