import React from "react";
import {
  Phone,
  MessageCircle,
  Briefcase,
  Settings,
  GraduationCap,
  ArrowRightLeft,
  Bell,
  Play,
  Shield,
  UserCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";

const SIGNAL_CATEGORIES: Record<string, { icon: React.ElementType; color: string }> = {
  // Voice AI
  voice_call_initiated: { icon: Phone, color: "text-blue-500 bg-blue-50" },
  voice_call_outcome: { icon: Phone, color: "text-blue-500 bg-blue-50" },
  voice_conversation_analyzed: { icon: Phone, color: "text-blue-600 bg-blue-50" },
  voice_call_recording_stored: { icon: Phone, color: "text-blue-400 bg-blue-50" },
  // WhatsApp
  whatsapp_message_sent: { icon: MessageCircle, color: "text-green-500 bg-green-50" },
  whatsapp_message_delivered: { icon: MessageCircle, color: "text-green-500 bg-green-50" },
  whatsapp_message_read: { icon: MessageCircle, color: "text-green-600 bg-green-50" },
  whatsapp_agent_replied: { icon: MessageCircle, color: "text-green-700 bg-green-50" },
  whatsapp_training_interaction: { icon: GraduationCap, color: "text-green-500 bg-green-50" },
  // ADM Activity
  adm_agent_call_logged: { icon: UserCheck, color: "text-purple-500 bg-purple-50" },
  adm_agent_visit_logged: { icon: UserCheck, color: "text-purple-500 bg-purple-50" },
  adm_nudge_received: { icon: Bell, color: "text-purple-500 bg-purple-50" },
  adm_nudge_acted_on: { icon: UserCheck, color: "text-purple-600 bg-purple-50" },
  adm_briefing_opened: { icon: Bell, color: "text-purple-400 bg-purple-50" },
  // Business Events
  policy_sold: { icon: Briefcase, color: "text-amber-600 bg-amber-50" },
  commission_credited: { icon: Briefcase, color: "text-amber-500 bg-amber-50" },
  license_status_changed: { icon: Shield, color: "text-amber-500 bg-amber-50" },
  agent_data_updated: { icon: Settings, color: "text-gray-500 bg-gray-50" },
  training_completed_external: { icon: GraduationCap, color: "text-amber-500 bg-amber-50" },
  // System Events
  lifecycle_state_changed: { icon: ArrowRightLeft, color: "text-indigo-500 bg-indigo-50" },
  playbook_started: { icon: Play, color: "text-indigo-500 bg-indigo-50" },
  playbook_step_executed: { icon: Play, color: "text-indigo-500 bg-indigo-50" },
  playbook_completed: { icon: Play, color: "text-indigo-600 bg-indigo-50" },
  escalation_created: { icon: Bell, color: "text-red-500 bg-red-50" },
  consent_changed: { icon: Shield, color: "text-gray-500 bg-gray-50" },
};

const DEFAULT_SIGNAL = { icon: Settings, color: "text-gray-400 bg-gray-50" };

interface SignalIconProps {
  signalType: string;
  size?: "sm" | "md";
  className?: string;
}

export function SignalIcon({ signalType, size = "md", className }: SignalIconProps) {
  const config = SIGNAL_CATEGORIES[signalType] ?? DEFAULT_SIGNAL;
  const Icon = config.icon;
  const iconSize = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4";
  const padding = size === "sm" ? "p-1" : "p-1.5";

  return (
    <span className={cn("inline-flex items-center rounded-full", config.color, padding, className)}>
      <Icon className={iconSize} />
    </span>
  );
}

export function getSignalCategory(signalType: string): string {
  if (signalType.startsWith("voice_")) return "Voice AI";
  if (signalType.startsWith("whatsapp_")) return "WhatsApp";
  if (signalType.startsWith("adm_")) return "ADM";
  if (signalType.startsWith("playbook_")) return "Playbook";
  if (
    ["policy_sold", "commission_credited", "license_status_changed", "agent_data_updated", "training_completed_external"].includes(signalType)
  )
    return "Business";
  return "System";
}
