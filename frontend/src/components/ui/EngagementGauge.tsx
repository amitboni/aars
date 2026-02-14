"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface EngagementGaugeProps {
  score: number;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  className?: string;
}

export function EngagementGauge({
  score,
  size = "md",
  showLabel = true,
  className,
}: EngagementGaugeProps) {
  const capped = Math.min(Math.max(score, 0), 100);
  const radius = size === "lg" ? 40 : size === "md" ? 32 : 24;
  const stroke = size === "lg" ? 6 : size === "md" ? 5 : 4;
  const viewSize = (radius + stroke) * 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (capped / 100) * circumference;

  const color =
    capped > 60
      ? "stroke-emerald-500"
      : capped >= 30
      ? "stroke-amber-400"
      : "stroke-red-500";

  const textColor =
    capped > 60
      ? "text-emerald-600"
      : capped >= 30
      ? "text-amber-500"
      : "text-red-500";

  const fontSize = size === "lg" ? "text-lg" : size === "md" ? "text-sm" : "text-xs";

  return (
    <div className={cn("inline-flex flex-col items-center", className)}>
      <svg
        width={viewSize}
        height={viewSize}
        className="-rotate-90"
      >
        <circle
          cx={radius + stroke}
          cy={radius + stroke}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={stroke}
        />
        <circle
          cx={radius + stroke}
          cy={radius + stroke}
          r={radius}
          fill="none"
          className={color}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
      </svg>
      <span className={cn("mt-1 font-bold", fontSize, textColor)}>
        {capped.toFixed(0)}
      </span>
      {showLabel && (
        <span className="text-[10px] text-gray-400">Engagement</span>
      )}
    </div>
  );
}
