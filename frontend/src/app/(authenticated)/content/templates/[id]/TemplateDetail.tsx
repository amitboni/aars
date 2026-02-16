"use client";

import React, { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Tabs } from "@/components/ui/Tabs";
import { FormField } from "@/components/ui/FormField";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useApi } from "@/hooks/useApi";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { MessageTemplate } from "@/lib/types";
import { ArrowLeft } from "lucide-react";

const STATUS_VARIANT: Record<string, "success" | "info" | "warning" | "danger" | "default"> = {
  draft: "default",
  approved: "info",
  active: "success",
  archived: "warning",
};

const TABS = [
  { id: "details", label: "Details" },
  { id: "preview", label: "Preview" },
  { id: "versions", label: "Versions" },
];

export default function TemplateDetail() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const { toast } = useToast();

  const { data: template, isLoading, error, refetch } = useApi(
    () => api.templates.get(id),
    [id]
  );
  const { data: versions } = useApi(() => api.templates.versions(id), [id]);

  const [activeTab, setActiveTab] = useState("details");
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Edit form state
  const [editName, setEditName] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [editDescription, setEditDescription] = useState("");

  // Preview state
  const [previewLang, setPreviewLang] = useState("hi");
  const [previewParams, setPreviewParams] = useState<Record<string, string>>({});
  const [previewResult, setPreviewResult] = useState<{ rendered: string; buttons: unknown[] } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const startEdit = (t: MessageTemplate) => {
    setEditName(t.name);
    setEditCategory(t.category);
    setEditDescription(t.description ?? "");
    setEditing(true);
  };

  const saveEdit = async () => {
    setActionLoading(true);
    try {
      await api.templates.update(id, {
        name: editName.trim() || undefined,
        category: editCategory || undefined,
        description: editDescription.trim() || undefined,
      });
      toast("Template updated", "success");
      setEditing(false);
      refetch();
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message : "Failed to update";
      toast(message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleStatusAction = async (action: "approve" | "activate" | "archive") => {
    setActionLoading(true);
    try {
      const fn = action === "approve" ? api.templates.approve
        : action === "activate" ? api.templates.activate
        : api.templates.archive;
      await fn(id);
      toast(`Template ${action}d`, "success");
      refetch();
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message : `Failed to ${action}`;
      toast(message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    setActionLoading(true);
    try {
      await api.templates.delete(id);
      toast("Template deleted", "success");
      router.push("/content/templates");
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message : "Failed to delete";
      toast(message, "error");
    } finally {
      setActionLoading(false);
      setDeleting(false);
    }
  };

  const runPreview = async () => {
    setPreviewLoading(true);
    try {
      const result = await api.templates.preview(id, previewLang, previewParams);
      setPreviewResult(result);
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message : "Preview failed";
      toast(message, "error");
    } finally {
      setPreviewLoading(false);
    }
  };

  if (isLoading) return <LoadingSpinner text="Loading template..." />;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!template) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push("/content/templates")}
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">{template.name}</h1>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant={STATUS_VARIANT[template.status] ?? "default"}>
              {template.status}
            </Badge>
            <span className="text-sm text-gray-500">v{template.version}</span>
          </div>
        </div>
      </div>

      <Tabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === "details" && (
        <Card>
          {editing ? (
            <div className="space-y-4">
              <FormField label="Name" htmlFor="edit-name" required>
                <input
                  id="edit-name"
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </FormField>
              <FormField label="Category" htmlFor="edit-category">
                <input
                  id="edit-category"
                  type="text"
                  value={editCategory}
                  onChange={(e) => setEditCategory(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </FormField>
              <FormField label="Description" htmlFor="edit-desc">
                <textarea
                  id="edit-desc"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={3}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </FormField>
              <div className="flex gap-3">
                <Button onClick={saveEdit} loading={actionLoading}>Save</Button>
                <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="divide-y divide-gray-100">
                <div className="flex justify-between py-3 text-sm">
                  <span className="text-gray-500">Category</span>
                  <Badge variant="info">{template.category}</Badge>
                </div>
                <div className="flex justify-between py-3 text-sm">
                  <span className="text-gray-500">Description</span>
                  <span className="font-medium text-gray-900">{template.description ?? "—"}</span>
                </div>
                <div className="flex justify-between py-3 text-sm">
                  <span className="text-gray-500">Default</span>
                  <span className="font-medium text-gray-900">{template.is_default ? "Yes" : "No"}</span>
                </div>
                <div className="flex justify-between py-3 text-sm">
                  <span className="text-gray-500">Placeholders</span>
                  <span className="font-mono text-xs text-gray-600">
                    {template.placeholders.length > 0 ? template.placeholders.join(", ") : "—"}
                  </span>
                </div>
                <div className="flex justify-between py-3 text-sm">
                  <span className="text-gray-500">Languages</span>
                  <span className="text-xs text-gray-600">
                    {Object.keys(template.language_variants).join(", ") || "—"}
                  </span>
                </div>
                <div className="flex justify-between py-3 text-sm">
                  <span className="text-gray-500">Created</span>
                  <span className="text-gray-600">{formatDate(template.created_at)}</span>
                </div>
                <div className="flex justify-between py-3 text-sm">
                  <span className="text-gray-500">Updated</span>
                  <span className="text-gray-600">{formatDate(template.updated_at)}</span>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 border-t pt-4">
                <Button variant="secondary" onClick={() => startEdit(template)}>Edit</Button>
                {template.status === "draft" && (
                  <Button onClick={() => handleStatusAction("approve")} loading={actionLoading}>
                    Approve
                  </Button>
                )}
                {template.status === "approved" && (
                  <Button onClick={() => handleStatusAction("activate")} loading={actionLoading}>
                    Activate
                  </Button>
                )}
                {template.status === "active" && (
                  <Button variant="secondary" onClick={() => handleStatusAction("archive")} loading={actionLoading}>
                    Archive
                  </Button>
                )}
                <Button variant="danger" onClick={() => setDeleting(true)}>Delete</Button>
              </div>
            </div>
          )}
        </Card>
      )}

      {activeTab === "preview" && (
        <Card>
          <div className="space-y-4">
            <div className="flex gap-3">
              <FormField label="Language" htmlFor="preview-lang">
                <select
                  id="preview-lang"
                  value={previewLang}
                  onChange={(e) => setPreviewLang(e.target.value)}
                  className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  {Object.keys(template.language_variants).length > 0
                    ? Object.keys(template.language_variants).map((lang) => (
                        <option key={lang} value={lang}>
                          {lang}
                        </option>
                      ))
                    : <option value="hi">hi</option>}
                </select>
              </FormField>
            </div>

            {template.placeholders.length > 0 && (
              <div className="grid grid-cols-2 gap-3">
                {template.placeholders.map((p) => (
                  <FormField key={p} label={p} htmlFor={`param-${p}`}>
                    <input
                      id={`param-${p}`}
                      type="text"
                      value={previewParams[p] ?? ""}
                      onChange={(e) =>
                        setPreviewParams((prev) => ({ ...prev, [p]: e.target.value }))
                      }
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      placeholder={`Value for ${p}`}
                    />
                  </FormField>
                ))}
              </div>
            )}

            <Button onClick={runPreview} loading={previewLoading}>
              Generate Preview
            </Button>

            {previewResult && (
              <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
                <h4 className="mb-2 text-sm font-semibold text-gray-900">Rendered Output</h4>
                <p className="whitespace-pre-wrap text-sm text-gray-700">{previewResult.rendered}</p>
                {previewResult.buttons.length > 0 && (
                  <div className="mt-3 space-y-1">
                    <p className="text-xs font-medium text-gray-500">Buttons:</p>
                    {previewResult.buttons.map((btn, i) => (
                      <div key={i} className="rounded border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-700">
                        {JSON.stringify(btn)}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      )}

      {activeTab === "versions" && (
        <Card>
          {!versions || versions.length === 0 ? (
            <p className="text-sm text-gray-500">No version history</p>
          ) : (
            <div className="space-y-2">
              {versions.map((v) => (
                <div
                  key={v.id}
                  className="flex items-center justify-between rounded-md border border-gray-100 px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-medium text-gray-900">v{v.version}</span>
                    <Badge variant={STATUS_VARIANT[v.status] ?? "default"}>
                      {v.status}
                    </Badge>
                  </div>
                  <span className="text-xs text-gray-500">{formatDate(v.created_at)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <ConfirmDialog
        open={deleting}
        onClose={() => setDeleting(false)}
        onConfirm={handleDelete}
        title="Delete Template"
        message={`Are you sure you want to delete "${template.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        loading={actionLoading}
      />
    </div>
  );
}
