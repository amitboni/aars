"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FormField } from "@/components/ui/FormField";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { ArrowLeft } from "lucide-react";

const CATEGORY_OPTIONS = [
  "onboarding",
  "reactivation",
  "training",
  "nudge",
  "celebration",
  "reminder",
];

export default function CreateTemplatePage() {
  const router = useRouter();
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState("");
  const [category, setCategory] = useState("onboarding");
  const [description, setDescription] = useState("");
  const [placeholders, setPlaceholders] = useState("");
  const [languageKey, setLanguageKey] = useState("hi");
  const [languageValue, setLanguageValue] = useState("");
  const [languageVariants, setLanguageVariants] = useState<Record<string, string>>({});

  const addLanguageVariant = () => {
    if (!languageKey.trim() || !languageValue.trim()) return;
    setLanguageVariants((prev) => ({ ...prev, [languageKey.trim()]: languageValue.trim() }));
    setLanguageValue("");
  };

  const removeLanguageVariant = (key: string) => {
    setLanguageVariants((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      const template = await api.templates.create({
        name: name.trim(),
        category,
        description: description.trim() || undefined,
        language_variants: Object.keys(languageVariants).length > 0 ? languageVariants : undefined,
        placeholders: placeholders
          .split(",")
          .map((p) => p.trim())
          .filter(Boolean),
      });
      toast("Template created successfully", "success");
      router.push(`/content/templates/${template.id}`);
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message
        : "Failed to create template";
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push("/content/templates")}
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Create Template</h1>
      </div>

      <Card>
        <form onSubmit={handleSubmit} className="space-y-5">
          <FormField label="Name" htmlFor="name" required>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Template name"
              required
            />
          </FormField>

          <FormField label="Category" htmlFor="category" required>
            <select
              id="category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {CATEGORY_OPTIONS.map((c) => (
                <option key={c} value={c}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Description" htmlFor="description">
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Optional description"
            />
          </FormField>

          <FormField label="Placeholders" htmlFor="placeholders" hint="Comma-separated, e.g. agent_name, policy_type">
            <input
              id="placeholders"
              type="text"
              value={placeholders}
              onChange={(e) => setPlaceholders(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="agent_name, policy_type"
            />
          </FormField>

          <FormField label="Language Variants" htmlFor="lang-key">
            <div className="space-y-2">
              <div className="flex gap-2">
                <input
                  id="lang-key"
                  type="text"
                  value={languageKey}
                  onChange={(e) => setLanguageKey(e.target.value)}
                  className="w-20 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder="hi"
                />
                <input
                  type="text"
                  value={languageValue}
                  onChange={(e) => setLanguageValue(e.target.value)}
                  className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder="Message body text..."
                />
                <Button type="button" variant="secondary" size="sm" onClick={addLanguageVariant}>
                  Add
                </Button>
              </div>
              {Object.entries(languageVariants).map(([key, val]) => (
                <div
                  key={key}
                  className="flex items-center gap-2 rounded-md border border-gray-100 px-3 py-2"
                >
                  <span className="font-mono text-xs font-medium text-blue-600">{key}</span>
                  <span className="flex-1 truncate text-sm text-gray-700">{val}</span>
                  <button
                    type="button"
                    onClick={() => removeLanguageVariant(key)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </FormField>

          <div className="flex justify-end gap-3 border-t pt-4">
            <Button
              type="button"
              variant="secondary"
              onClick={() => router.push("/content/templates")}
            >
              Cancel
            </Button>
            <Button type="submit" loading={saving} disabled={!name.trim()}>
              Create Template
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
