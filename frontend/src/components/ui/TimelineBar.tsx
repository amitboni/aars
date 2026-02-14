import React from "react";
import { cn, lifecycleBadgeColor, formatDate } from "@/lib/utils";
import type { LifecycleState } from "@/lib/types";

export interface TimelineStep {
  state: LifecycleState;
  date: string;
}

interface TimelineBarProps {
  steps: TimelineStep[];
  className?: string;
}

const LIFECYCLE_DOT_COLORS: Record<LifecycleState, string> = {
  onboarded: "bg-gray-400",
  licensed: "bg-blue-500",
  first_sale: "bg-purple-500",
  active: "bg-emerald-500",
  productive: "bg-emerald-600",
  at_risk: "bg-amber-500",
  dormant: "bg-red-500",
  lapsed: "bg-gray-400",
  terminated: "bg-gray-700",
};

export function TimelineBar({ steps, className }: TimelineBarProps) {
  if (steps.length === 0) return null;

  return (
    <div className={cn("flex items-start gap-0 overflow-x-auto", className)}>
      {steps.map((step, idx) => (
        <div key={`${step.state}-${idx}`} className="flex items-start">
          {/* Node */}
          <div className="flex flex-col items-center">
            <div
              className={cn(
                "h-3.5 w-3.5 rounded-full border-2 border-white shadow-sm",
                LIFECYCLE_DOT_COLORS[step.state]
              )}
            />
            <div className="mt-1.5 text-center">
              <span
                className={cn(
                  "inline-block rounded-full px-2 py-0.5 text-[10px] font-medium",
                  lifecycleBadgeColor(step.state)
                )}
              >
                {step.state.replace(/_/g, " ")}
              </span>
              <p className="mt-0.5 text-[10px] text-gray-400 whitespace-nowrap">
                {formatDate(step.date)}
              </p>
            </div>
          </div>
          {/* Connector */}
          {idx < steps.length - 1 && (
            <div className="mt-1.5 h-px w-8 flex-shrink-0 bg-gray-300 sm:w-12" />
          )}
        </div>
      ))}
    </div>
  );
}
