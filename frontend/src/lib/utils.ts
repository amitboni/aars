import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { LifecycleState } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diff = now - then;

  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;

  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;

  const years = Math.floor(months / 12);
  return `${years}y ago`;
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-IN").format(n);
}

export function maskPhone(phone: string | null | undefined): string {
  if (!phone) return "—";
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 4) return phone;
  return phone.slice(0, phone.length - 4).replace(/\d/g, "X") + phone.slice(-4);
}

export function daysAgo(iso: string | null | undefined): number {
  if (!iso) return 0;
  const diff = Date.now() - new Date(iso).getTime();
  return Math.floor(diff / 86400000);
}

export function engagementColor(score: number): string {
  if (score > 60) return "text-emerald-600";
  if (score >= 30) return "text-amber-500";
  return "text-red-500";
}

export function engagementBgColor(score: number): string {
  if (score > 60) return "bg-emerald-500";
  if (score >= 30) return "bg-amber-400";
  return "bg-red-500";
}

const LIFECYCLE_COLORS: Record<LifecycleState, string> = {
  onboarded: "text-gray-500",
  licensed: "text-blue-500",
  first_sale: "text-purple-500",
  active: "text-emerald-500",
  productive: "text-emerald-600",
  at_risk: "text-amber-500",
  dormant: "text-red-500",
  lapsed: "text-gray-400",
  terminated: "text-gray-700",
};

const LIFECYCLE_BADGE_COLORS: Record<LifecycleState, string> = {
  onboarded: "bg-gray-100 text-gray-700",
  licensed: "bg-blue-100 text-blue-700",
  first_sale: "bg-purple-100 text-purple-700",
  active: "bg-emerald-100 text-emerald-700",
  productive: "bg-emerald-100 text-emerald-800",
  at_risk: "bg-amber-100 text-amber-700",
  dormant: "bg-red-100 text-red-700",
  lapsed: "bg-gray-100 text-gray-500",
  terminated: "bg-gray-200 text-gray-700",
};

export function lifecycleColor(state: LifecycleState): string {
  return LIFECYCLE_COLORS[state] ?? "text-gray-500";
}

export function lifecycleBadgeColor(state: LifecycleState): string {
  return LIFECYCLE_BADGE_COLORS[state] ?? "bg-gray-100 text-gray-700";
}
