"use client";

import React from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import type { SettingFieldMetadata } from "@/lib/types";

interface SettingsDiffModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  sectionName: string;
  currentValues: Record<string, unknown>;
  proposedValues: Record<string, unknown>;
  metadata: Record<string, SettingFieldMetadata>;
  loading: boolean;
}

function formatValue(v: unknown): string {
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return String(v);
}

export function SettingsDiffModal({
  open,
  onClose,
  onConfirm,
  sectionName,
  currentValues,
  proposedValues,
  metadata,
  loading,
}: SettingsDiffModalProps) {
  const changedKeys = Object.keys(proposedValues).filter(
    (k) => JSON.stringify(proposedValues[k]) !== JSON.stringify(currentValues[k])
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Review Changes"
      subtitle={sectionName
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ")}
      maxWidth="lg"
    >
      {changedKeys.length === 0 ? (
        <p className="text-sm text-gray-500">No changes detected.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Setting
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Current
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  New
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {changedKeys.map((key) => {
                const meta = metadata[key];
                return (
                  <tr key={key}>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {meta?.description ?? key}
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-red-50 px-2 py-0.5 text-sm text-red-700">
                        {formatValue(currentValues[key])}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-emerald-50 px-2 py-0.5 text-sm text-emerald-700">
                        {formatValue(proposedValues[key])}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-6 flex justify-end gap-3">
        <Button variant="secondary" onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button onClick={onConfirm} loading={loading} disabled={changedKeys.length === 0}>
          Confirm &amp; Send OTP
        </Button>
      </div>
    </Modal>
  );
}
