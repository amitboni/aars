import React from "react";
import { Button } from "./Button";

interface PaginationProps {
  hasMore: boolean;
  isLoading: boolean;
  onLoadMore: () => void;
  count?: number;
}

export function Pagination({ hasMore, isLoading, onLoadMore, count }: PaginationProps) {
  if (!hasMore && !count) return null;

  return (
    <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3">
      {count !== undefined && (
        <span className="text-sm text-gray-500">
          Showing {count} {count === 1 ? "item" : "items"}
        </span>
      )}
      {hasMore && (
        <Button
          variant="secondary"
          size="sm"
          loading={isLoading}
          onClick={onLoadMore}
          className="ml-auto"
        >
          Load More
        </Button>
      )}
    </div>
  );
}
