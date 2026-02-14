import React from "react";
import { cn } from "@/lib/utils";
import { lifecycleBadgeColor } from "@/lib/utils";
import type { LifecycleState } from "@/lib/types";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info" | "lifecycle";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  lifecycleState?: LifecycleState;
  className?: string;
}

const variantClasses: Record<Exclude<BadgeVariant, "lifecycle">, string> = {
  default: "bg-gray-100 text-gray-700",
  success: "bg-emerald-100 text-emerald-700",
  warning: "bg-amber-100 text-amber-700",
  danger: "bg-red-100 text-red-700",
  info: "bg-blue-100 text-blue-700",
};

export function Badge({ children, variant = "default", lifecycleState, className }: BadgeProps) {
  const colorClass =
    variant === "lifecycle" && lifecycleState
      ? lifecycleBadgeColor(lifecycleState)
      : variantClasses[variant === "lifecycle" ? "default" : variant];

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        colorClass,
        className
      )}
    >
      {children}
    </span>
  );
}
