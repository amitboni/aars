import React from "react";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  trend?: {
    direction: "up" | "down" | "stable";
    label?: string;
  };
  subtitle?: string;
  className?: string;
  onClick?: () => void;
}

const trendConfig = {
  up: { icon: TrendingUp, color: "text-emerald-600", bg: "bg-emerald-50" },
  down: { icon: TrendingDown, color: "text-red-600", bg: "bg-red-50" },
  stable: { icon: Minus, color: "text-gray-500", bg: "bg-gray-50" },
};

export function StatCard({
  label,
  value,
  icon,
  trend,
  subtitle,
  className,
  onClick,
}: StatCardProps) {
  const Wrapper = onClick ? "button" : "div";
  return (
    <Wrapper
      className={cn(
        "rounded-lg border border-gray-200 bg-white p-5 shadow-sm text-left",
        onClick && "cursor-pointer transition-shadow hover:shadow-md",
        className
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-500">{label}</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
          {subtitle && (
            <p className="mt-0.5 text-xs text-gray-400">{subtitle}</p>
          )}
        </div>
        {icon && (
          <div className="ml-3 flex-shrink-0 rounded-lg bg-gray-50 p-2.5 text-gray-400">
            {icon}
          </div>
        )}
      </div>
      {trend && (
        <div className="mt-3 flex items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center rounded-full px-1.5 py-0.5",
              trendConfig[trend.direction].bg
            )}
          >
            {React.createElement(trendConfig[trend.direction].icon, {
              className: cn("h-3.5 w-3.5", trendConfig[trend.direction].color),
            })}
          </span>
          {trend.label && (
            <span
              className={cn(
                "text-xs font-medium",
                trendConfig[trend.direction].color
              )}
            >
              {trend.label}
            </span>
          )}
        </div>
      )}
    </Wrapper>
  );
}
