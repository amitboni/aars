import React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  text?: string;
  className?: string;
}

export function LoadingSpinner({ text, className }: LoadingSpinnerProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-12", className)}>
      <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      {text && <p className="mt-3 text-sm text-gray-500">{text}</p>}
    </div>
  );
}
