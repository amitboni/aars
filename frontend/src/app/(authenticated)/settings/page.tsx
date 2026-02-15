"use client";

import React, { useState } from "react";
import { Tabs } from "@/components/ui/Tabs";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { SettingsSectionCard } from "@/components/settings/SettingsSectionCard";
import { SettingsDiffModal } from "@/components/settings/SettingsDiffModal";
import { OtpVerificationModal } from "@/components/settings/OtpVerificationModal";
import { SettingsAuditLog } from "@/components/settings/SettingsAuditLog";
import { useApi } from "@/hooks/useApi";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { SettingsSectionName, SettingsSection, SettingFieldMetadata } from "@/lib/types";

const SECTION_ORDER: SettingsSectionName[] = [
  "lifecycle_thresholds",
  "engagement_scoring_weights",
  "contact_rules",
  "trai_calling_hours",
  "rate_limits",
  "branding",
  "languages",
];

const PAGE_TABS = [
  { id: "configuration", label: "Configuration" },
  { id: "audit", label: "Audit Log" },
];

export default function SettingsPage() {
  const { toast } = useToast();
  const { data: allSettings, isLoading, error, refetch } = useApi(
    () => api.settings.getAll(),
    []
  );

  const [activeTab, setActiveTab] = useState("configuration");
  const [editingSection, setEditingSection] = useState<SettingsSectionName | null>(null);
  const [editValues, setEditValues] = useState<Record<string, unknown>>({});

  // Diff modal state
  const [showDiff, setShowDiff] = useState(false);
  const [diffLoading, setDiffLoading] = useState(false);

  // OTP modal state
  const [showOtp, setShowOtp] = useState(false);
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);
  const [changeRequestId, setChangeRequestId] = useState<string>("");
  const [maskedEmail, setMaskedEmail] = useState("");
  const [otpExpiresAt, setOtpExpiresAt] = useState("");

  const startEdit = (sectionName: SettingsSectionName, section: SettingsSection) => {
    setEditingSection(sectionName);
    setEditValues({ ...section.values });
  };

  const cancelEdit = () => {
    setEditingSection(null);
    setEditValues({});
  };

  const handleChange = (key: string, value: unknown) => {
    setEditValues((prev) => ({ ...prev, [key]: value }));
  };

  const openDiffModal = () => {
    setShowDiff(true);
  };

  const handleConfirmDiff = async () => {
    if (!editingSection || !allSettings) return;
    const section = allSettings[editingSection];
    if (!section) return;

    // Compute only changed fields
    const changes: Record<string, unknown> = {};
    for (const key of Object.keys(editValues)) {
      if (JSON.stringify(editValues[key]) !== JSON.stringify(section.values[key])) {
        changes[key] = editValues[key];
      }
    }

    if (Object.keys(changes).length === 0) {
      toast("No changes to submit", "warning");
      setShowDiff(false);
      return;
    }

    setDiffLoading(true);
    try {
      const response = await api.settings.requestChange(editingSection, changes);
      setChangeRequestId(response.change_request_id);
      setMaskedEmail(response.otp_sent_to);
      setOtpExpiresAt(response.expires_at);
      setShowDiff(false);
      setShowOtp(true);
      setOtpError(null);
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message
        : "Failed to request change";
      toast(message, "error");
    } finally {
      setDiffLoading(false);
    }
  };

  const handleVerifyOtp = async (otp: string) => {
    setOtpLoading(true);
    setOtpError(null);
    try {
      await api.settings.verifyOtp(changeRequestId, otp);
      toast("Settings updated successfully", "success");
      setShowOtp(false);
      setEditingSection(null);
      setEditValues({});
      refetch();
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message
        : "Invalid OTP";
      setOtpError(message);
    } finally {
      setOtpLoading(false);
    }
  };

  const handleCancelOtp = async () => {
    if (!editingSection) return;
    try {
      await api.settings.cancelRequest(editingSection, changeRequestId);
      toast("Change request cancelled", "info");
    } catch {
      // ignore cancel errors
    }
    setShowOtp(false);
    setOtpError(null);
  };

  if (isLoading) return <LoadingSpinner text="Loading settings..." />;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!allSettings) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      <Tabs tabs={PAGE_TABS} activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === "configuration" && (
        <div className="space-y-6">
          {SECTION_ORDER.map((sectionName) => {
            const section = allSettings[sectionName];
            if (!section) return null;
            const isEditing = editingSection === sectionName;

            return (
              <SettingsSectionCard
                key={sectionName}
                sectionName={sectionName}
                section={section}
                isEditing={isEditing}
                editValues={isEditing ? editValues : {}}
                onStartEdit={() => startEdit(sectionName, section)}
                onCancelEdit={cancelEdit}
                onChange={handleChange}
                onReviewChanges={openDiffModal}
                saving={diffLoading}
              />
            );
          })}
        </div>
      )}

      {activeTab === "audit" && <SettingsAuditLog />}

      {/* Diff Modal */}
      {editingSection && allSettings[editingSection] && (
        <SettingsDiffModal
          open={showDiff}
          onClose={() => setShowDiff(false)}
          onConfirm={handleConfirmDiff}
          sectionName={editingSection}
          currentValues={allSettings[editingSection]!.values}
          proposedValues={editValues}
          metadata={(allSettings[editingSection]!.metadata ?? {}) as Record<string, SettingFieldMetadata>}
          loading={diffLoading}
        />
      )}

      {/* OTP Modal */}
      <OtpVerificationModal
        open={showOtp}
        onClose={() => setShowOtp(false)}
        onVerify={handleVerifyOtp}
        onCancel={handleCancelOtp}
        maskedEmail={maskedEmail}
        expiresAt={otpExpiresAt}
        loading={otpLoading}
        error={otpError}
      />
    </div>
  );
}
