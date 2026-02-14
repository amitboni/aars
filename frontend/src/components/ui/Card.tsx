import React from "react";
import { cn } from "@/lib/utils";

interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  padding?: boolean;
}

export function Card({ title, children, className, padding = true }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-gray-200 bg-white shadow-sm",
        padding && "p-6",
        className
      )}
    >
      {title && (
        <h3 className="mb-4 text-sm font-semibold text-gray-900">{title}</h3>
      )}
      {children}
    </div>
  );
}
