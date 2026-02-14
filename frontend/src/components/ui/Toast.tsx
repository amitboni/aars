"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { X, CheckCircle, AlertTriangle, Info, XCircle } from "lucide-react";

type ToastVariant = "success" | "error" | "warning" | "info";

interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}

const VARIANT_STYLES: Record<ToastVariant, { bg: string; icon: React.ReactNode }> = {
  success: {
    bg: "bg-emerald-50 border-emerald-200 text-emerald-800",
    icon: <CheckCircle className="h-5 w-5 text-emerald-500" />,
  },
  error: {
    bg: "bg-red-50 border-red-200 text-red-800",
    icon: <XCircle className="h-5 w-5 text-red-500" />,
  },
  warning: {
    bg: "bg-amber-50 border-amber-200 text-amber-800",
    icon: <AlertTriangle className="h-5 w-5 text-amber-500" />,
  },
  info: {
    bg: "bg-blue-50 border-blue-200 text-blue-800",
    icon: <Info className="h-5 w-5 text-blue-500" />,
  },
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, variant: ToastVariant = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg transition-all animate-in slide-in-from-right",
              VARIANT_STYLES[t.variant].bg
            )}
          >
            {VARIANT_STYLES[t.variant].icon}
            <p className="text-sm font-medium">{t.message}</p>
            <button
              onClick={() => dismiss(t.id)}
              className="ml-2 rounded p-0.5 opacity-60 hover:opacity-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
