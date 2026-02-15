"use client";

import React, { useState, useCallback, useEffect } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Tabs } from "@/components/ui/Tabs";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar, FilterSelect } from "@/components/ui/FilterBar";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { FormField } from "@/components/ui/FormField";
import { Modal } from "@/components/ui/Modal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useApi } from "@/hooks/useApi";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { formatDate, cn } from "@/lib/utils";
import type {
  TrainingModuleSummary,
  TrainingModule,
  Quiz,
  QuizQuestion,
  TrainingProgress,
} from "@/lib/types";
import { Plus, Clock, Users, X } from "lucide-react";

const DIFFICULTY_OPTIONS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
];

const DIFFICULTY_VARIANT: Record<string, "success" | "warning" | "danger" | "default"> = {
  beginner: "success",
  intermediate: "warning",
  advanced: "danger",
};

// ─── Module Detail Modal ────────────────────────────────────────────────────

function ModuleDetail({
  moduleId,
  onClose,
  onRefreshList,
}: {
  moduleId: string;
  onClose: () => void;
  onRefreshList: () => void;
}) {
  const { toast } = useToast();
  const { data: module, isLoading, refetch } = useApi(
    () => api.training.modules.get(moduleId),
    [moduleId]
  );
  const [activeTab, setActiveTab] = useState("overview");
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Edit state
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editTopic, setEditTopic] = useState("");
  const [editDifficulty, setEditDifficulty] = useState("");
  const [editDuration, setEditDuration] = useState(1);

  const startEdit = (m: TrainingModule) => {
    setEditTitle(m.title);
    setEditDescription(m.description ?? "");
    setEditTopic(m.topic);
    setEditDifficulty(m.difficulty);
    setEditDuration(m.duration_minutes);
    setEditing(true);
  };

  const saveEdit = async () => {
    setActionLoading(true);
    try {
      await api.training.modules.update(moduleId, {
        title: editTitle.trim() || undefined,
        description: editDescription.trim() || undefined,
        topic: editTopic.trim() || undefined,
        difficulty: editDifficulty || undefined,
        duration_minutes: editDuration,
      });
      toast("Module updated", "success");
      setEditing(false);
      refetch();
      onRefreshList();
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message : "Failed to update";
      toast(message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const toggleActive = async () => {
    if (!module) return;
    setActionLoading(true);
    try {
      await api.training.modules.update(moduleId, { is_active: !module.is_active });
      toast(module.is_active ? "Module deactivated" : "Module activated", "success");
      refetch();
      onRefreshList();
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message : "Failed to toggle";
      toast(message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    setActionLoading(true);
    try {
      await api.training.modules.delete(moduleId);
      toast("Module deleted", "success");
      onClose();
      onRefreshList();
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message : "Failed to delete";
      toast(message, "error");
    } finally {
      setActionLoading(false);
      setDeleting(false);
    }
  };

  if (isLoading) return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="rounded-lg bg-white p-8">
        <LoadingSpinner text="Loading module..." />
      </div>
    </div>
  );
  if (!module) return null;

  const DETAIL_TABS = [
    { id: "overview", label: "Overview" },
    { id: "quiz", label: "Quiz" },
    { id: "progress", label: "Progress" },
  ];

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white shadow-xl">
          <div className="sticky top-0 flex items-center justify-between border-b bg-white px-6 py-4">
            <div>
              <h2 className="text-lg font-bold text-gray-900">{module.title}</h2>
              <div className="mt-1 flex items-center gap-2">
                <Badge variant={DIFFICULTY_VARIANT[module.difficulty] ?? "default"}>
                  {module.difficulty}
                </Badge>
                <Badge variant={module.is_active ? "success" : "default"}>
                  {module.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
            </div>
            <button
              onClick={onClose}
              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="px-6 pt-4">
            <Tabs tabs={DETAIL_TABS} activeTab={activeTab} onChange={setActiveTab} />
          </div>

          <div className="space-y-4 p-6">
            {activeTab === "overview" && (
              editing ? (
                <div className="space-y-4">
                  <FormField label="Title" htmlFor="edit-title" required>
                    <input id="edit-title" type="text" value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </FormField>
                  <FormField label="Description" htmlFor="edit-desc">
                    <textarea id="edit-desc" value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)} rows={3}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </FormField>
                  <div className="grid grid-cols-3 gap-3">
                    <FormField label="Topic" htmlFor="edit-topic">
                      <input id="edit-topic" type="text" value={editTopic}
                        onChange={(e) => setEditTopic(e.target.value)}
                        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </FormField>
                    <FormField label="Difficulty" htmlFor="edit-diff">
                      <select id="edit-diff" value={editDifficulty}
                        onChange={(e) => setEditDifficulty(e.target.value)}
                        className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        {DIFFICULTY_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    </FormField>
                    <FormField label="Duration (min)" htmlFor="edit-dur">
                      <input id="edit-dur" type="number" min={1} value={editDuration}
                        onChange={(e) => setEditDuration(Number(e.target.value))}
                        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </FormField>
                  </div>
                  <div className="flex gap-3">
                    <Button onClick={saveEdit} loading={actionLoading}>Save</Button>
                    <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div className="rounded-lg bg-gray-50 p-3">
                      <div className="flex items-center justify-center gap-1 text-gray-500">
                        <Clock className="h-4 w-4" />
                      </div>
                      <p className="text-lg font-bold">{module.duration_minutes}m</p>
                      <p className="text-xs text-gray-500">Duration</p>
                    </div>
                    <div className="rounded-lg bg-gray-50 p-3">
                      <div className="flex items-center justify-center gap-1 text-gray-500">
                        <Users className="h-4 w-4" />
                      </div>
                      <p className="text-lg font-bold">{module.times_assigned}</p>
                      <p className="text-xs text-gray-500">Assigned</p>
                    </div>
                    <div className="rounded-lg bg-gray-50 p-3">
                      <p className="text-lg font-bold">{(module.effectiveness_score * 100).toFixed(0)}%</p>
                      <p className="text-xs text-gray-500">Effectiveness</p>
                    </div>
                  </div>
                  {module.description && (
                    <p className="text-sm text-gray-600">{module.description}</p>
                  )}
                  <div className="divide-y divide-gray-100">
                    <div className="flex justify-between py-3 text-sm">
                      <span className="text-gray-500">Topic</span>
                      <Badge variant="info">{module.topic}</Badge>
                    </div>
                    <div className="flex justify-between py-3 text-sm">
                      <span className="text-gray-500">Language</span>
                      <span className="font-medium text-gray-900">{module.language}</span>
                    </div>
                    <div className="flex justify-between py-3 text-sm">
                      <span className="text-gray-500">Content Type</span>
                      <span className="font-medium text-gray-900">{module.content_type}</span>
                    </div>
                    <div className="flex justify-between py-3 text-sm">
                      <span className="text-gray-500">Created</span>
                      <span className="text-gray-600">{formatDate(module.created_at)}</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 border-t pt-4">
                    <Button variant="secondary" onClick={() => startEdit(module)}>Edit</Button>
                    <Button
                      variant="secondary"
                      onClick={toggleActive}
                      loading={actionLoading}
                    >
                      {module.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    <Button variant="danger" onClick={() => setDeleting(true)}>Delete</Button>
                  </div>
                </div>
              )
            )}

            {activeTab === "quiz" && <QuizTab moduleId={moduleId} />}
            {activeTab === "progress" && <ProgressTab moduleId={moduleId} />}
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={deleting}
        onClose={() => setDeleting(false)}
        onConfirm={handleDelete}
        title="Delete Module"
        message={`Are you sure you want to delete "${module.title}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        loading={actionLoading}
      />
    </>
  );
}

// ─── Quiz Tab ───────────────────────────────────────────────────────────────

function QuizTab({ moduleId }: { moduleId: string }) {
  const { toast } = useToast();
  const { data: quiz, isLoading, refetch } = useApi(
    () => api.training.quiz.get(moduleId).catch(() => null),
    [moduleId]
  );
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [passingScore, setPassingScore] = useState(70);
  const [maxAttempts, setMaxAttempts] = useState(3);

  const startEditQuiz = (q: Quiz | null) => {
    setQuestions(q?.questions ?? [{ question: "", options: ["", "", "", ""], correct: 0, explanation: "" }]);
    setPassingScore(q?.passing_score ?? 70);
    setMaxAttempts(q?.max_attempts ?? 3);
    setEditing(true);
  };

  const updateQuestion = (idx: number, field: keyof QuizQuestion, value: unknown) => {
    setQuestions((prev) => prev.map((q, i) => i === idx ? { ...q, [field]: value } : q));
  };

  const updateOption = (qIdx: number, oIdx: number, value: string) => {
    setQuestions((prev) =>
      prev.map((q, i) =>
        i === qIdx ? { ...q, options: q.options.map((o, j) => (j === oIdx ? value : o)) } : q
      )
    );
  };

  const addQuestion = () => {
    setQuestions((prev) => [
      ...prev,
      { question: "", options: ["", "", "", ""], correct: 0, explanation: "" },
    ]);
  };

  const removeQuestion = (idx: number) => {
    setQuestions((prev) => prev.filter((_, i) => i !== idx));
  };

  const saveQuiz = async () => {
    const valid = questions.every(
      (q) => q.question.trim() && q.options.every((o) => o.trim())
    );
    if (!valid) {
      toast("Fill in all question and option fields", "error");
      return;
    }
    setSaving(true);
    try {
      await api.training.quiz.createOrUpdate(moduleId, {
        questions,
        passing_score: passingScore,
        max_attempts: maxAttempts,
      });
      toast("Quiz saved", "success");
      setEditing(false);
      refetch();
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message : "Failed to save quiz";
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) return <LoadingSpinner text="Loading quiz..." />;

  if (!editing) {
    if (!quiz) {
      return (
        <EmptyState
          message="No quiz configured"
          actionLabel="Create Quiz"
          onAction={() => startEditQuiz(null)}
        />
      );
    }

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex gap-3 text-sm text-gray-500">
            <span>Passing score: {quiz.passing_score}%</span>
            <span>Max attempts: {quiz.max_attempts}</span>
          </div>
          <Button variant="secondary" size="sm" onClick={() => startEditQuiz(quiz)}>
            Edit Quiz
          </Button>
        </div>
        <div className="space-y-3">
          {quiz.questions.map((q: QuizQuestion, i: number) => (
            <div key={i} className="rounded-md border border-gray-100 p-3">
              <p className="text-sm font-medium text-gray-900">
                {i + 1}. {q.question}
              </p>
              <ul className="mt-2 space-y-1">
                {q.options.map((opt: string, j: number) => (
                  <li
                    key={j}
                    className={cn(
                      "rounded px-2 py-1 text-sm",
                      j === q.correct
                        ? "bg-emerald-50 font-medium text-emerald-700"
                        : "text-gray-600"
                    )}
                  >
                    {String.fromCharCode(65 + j)}. {opt}
                  </li>
                ))}
              </ul>
              {q.explanation && (
                <p className="mt-2 text-xs text-gray-500">
                  Explanation: {q.explanation}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-4">
        <FormField label="Passing Score (%)" htmlFor="passing-score">
          <input
            id="passing-score"
            type="number"
            min={0}
            max={100}
            value={passingScore}
            onChange={(e) => setPassingScore(Number(e.target.value))}
            className="w-24 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </FormField>
        <FormField label="Max Attempts" htmlFor="max-attempts">
          <input
            id="max-attempts"
            type="number"
            min={1}
            value={maxAttempts}
            onChange={(e) => setMaxAttempts(Number(e.target.value))}
            className="w-24 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </FormField>
      </div>

      {questions.map((q, qIdx) => (
        <div key={qIdx} className="rounded-lg border border-gray-200 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-900">Question {qIdx + 1}</span>
            {questions.length > 1 && (
              <button
                onClick={() => removeQuestion(qIdx)}
                className="text-xs text-red-500 hover:text-red-700"
              >
                Remove
              </button>
            )}
          </div>
          <input
            type="text"
            value={q.question}
            onChange={(e) => updateQuestion(qIdx, "question", e.target.value)}
            placeholder="Question text"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="space-y-2">
            {q.options.map((opt, oIdx) => (
              <div key={oIdx} className="flex items-center gap-2">
                <input
                  type="radio"
                  name={`correct-${qIdx}`}
                  checked={q.correct === oIdx}
                  onChange={() => updateQuestion(qIdx, "correct", oIdx)}
                  className="text-blue-600 focus:ring-blue-500"
                />
                <input
                  type="text"
                  value={opt}
                  onChange={(e) => updateOption(qIdx, oIdx, e.target.value)}
                  placeholder={`Option ${String.fromCharCode(65 + oIdx)}`}
                  className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            ))}
          </div>
          <input
            type="text"
            value={q.explanation ?? ""}
            onChange={(e) => updateQuestion(qIdx, "explanation", e.target.value)}
            placeholder="Explanation (optional)"
            className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      ))}

      <Button variant="secondary" size="sm" onClick={addQuestion}>
        <Plus className="mr-1 h-4 w-4" />
        Add Question
      </Button>

      <div className="flex gap-3 border-t pt-4">
        <Button onClick={saveQuiz} loading={saving}>Save Quiz</Button>
        <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
      </div>
    </div>
  );
}

// ─── Progress Tab ───────────────────────────────────────────────────────────

function ProgressTab({ moduleId }: { moduleId: string }) {
  const [progressItems, setProgressItems] = useState<TrainingProgress[]>([]);
  const [cursor, setCursor] = useState<string | undefined>();
  const [loadingMore, setLoadingMore] = useState(false);

  const { data, isLoading } = useApi(
    () => api.training.progress.list({ module_id: moduleId, limit: 20 }),
    [moduleId]
  );

  useEffect(() => {
    if (data) {
      setProgressItems(data.data);
      setCursor(data.next_cursor ?? undefined);
    }
  }, [data]);

  const loadMore = useCallback(async () => {
    if (!cursor) return;
    setLoadingMore(true);
    try {
      const more = await api.training.progress.list({
        module_id: moduleId,
        cursor,
        limit: 20,
      });
      setProgressItems((prev) => [...prev, ...more.data]);
      setCursor(more.next_cursor ?? undefined);
    } finally {
      setLoadingMore(false);
    }
  }, [cursor, moduleId]);

  if (isLoading) return <LoadingSpinner text="Loading progress..." />;
  if (progressItems.length === 0) return <EmptyState message="No progress records" />;

  const STATUS_VARIANT: Record<string, "success" | "info" | "warning" | "danger" | "default"> = {
    completed: "success",
    in_progress: "info",
    assigned: "default",
    failed: "danger",
  };

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Agent</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Score</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Attempts</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {progressItems.map((p) => (
              <tr key={p.id}>
                <td className="px-4 py-3 font-mono text-xs text-gray-600">
                  {p.agent_id.slice(0, 8)}...
                </td>
                <td className="px-4 py-3">
                  <Badge variant={STATUS_VARIANT[p.status] ?? "default"}>
                    {p.status}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">
                  {p.score != null ? `${p.score.toFixed(0)}%` : "—"}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">{p.attempts}</td>
                <td className="px-4 py-3 text-xs text-gray-500">{formatDate(p.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination
        hasMore={!!cursor}
        isLoading={loadingMore}
        onLoadMore={loadMore}
        count={progressItems.length}
      />
    </div>
  );
}

// ─── Create Module Modal ────────────────────────────────────────────────────

function CreateModuleModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("beginner");
  const [duration, setDuration] = useState(10);
  const [language, setLanguage] = useState("hi");
  const [contentType, setContentType] = useState("video");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !topic.trim()) return;
    setSaving(true);
    try {
      await api.training.modules.create({
        title: title.trim(),
        description: description.trim() || undefined,
        topic: topic.trim(),
        difficulty,
        duration_minutes: duration,
        language,
        content_type: contentType,
      });
      toast("Module created", "success");
      onCreated();
      onClose();
      setTitle("");
      setDescription("");
      setTopic("");
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "message" in err
        ? (err as { message: string }).message : "Failed to create module";
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Create Training Module" maxWidth="lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label="Title" htmlFor="mod-title" required>
          <input id="mod-title" type="text" value={title}
            onChange={(e) => setTitle(e.target.value)} required
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="Module title"
          />
        </FormField>
        <FormField label="Description" htmlFor="mod-desc">
          <textarea id="mod-desc" value={description}
            onChange={(e) => setDescription(e.target.value)} rows={2}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="Optional description"
          />
        </FormField>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Topic" htmlFor="mod-topic" required>
            <input id="mod-topic" type="text" value={topic}
              onChange={(e) => setTopic(e.target.value)} required
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="e.g. product_knowledge"
            />
          </FormField>
          <FormField label="Difficulty" htmlFor="mod-diff">
            <select id="mod-diff" value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {DIFFICULTY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </FormField>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <FormField label="Duration (min)" htmlFor="mod-dur">
            <input id="mod-dur" type="number" min={1} value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </FormField>
          <FormField label="Language" htmlFor="mod-lang">
            <input id="mod-lang" type="text" value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </FormField>
          <FormField label="Content Type" htmlFor="mod-ct">
            <select id="mod-ct" value={contentType}
              onChange={(e) => setContentType(e.target.value)}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="video">Video</option>
              <option value="document">Document</option>
              <option value="interactive">Interactive</option>
            </select>
          </FormField>
        </div>
        <div className="flex justify-end gap-3 border-t pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={saving} disabled={!title.trim() || !topic.trim()}>
            Create Module
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function TrainingPage() {
  const [topicFilter, setTopicFilter] = useState("");
  const [difficultyFilter, setDifficultyFilter] = useState("");
  const [modules, setModules] = useState<TrainingModuleSummary[]>([]);
  const [cursor, setCursor] = useState<string | undefined>();
  const [loadingMore, setLoadingMore] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading, error, refetch } = useApi(
    () =>
      api.training.modules.list({
        topic: topicFilter || undefined,
        difficulty: difficultyFilter || undefined,
        limit: 50,
      }),
    [topicFilter, difficultyFilter]
  );

  useEffect(() => {
    if (data) {
      setModules(data.data);
      setCursor(data.next_cursor ?? undefined);
    }
  }, [data]);

  const loadMore = useCallback(async () => {
    if (!cursor) return;
    setLoadingMore(true);
    try {
      const more = await api.training.modules.list({
        topic: topicFilter || undefined,
        difficulty: difficultyFilter || undefined,
        cursor,
        limit: 50,
      });
      setModules((prev) => [...prev, ...more.data]);
      setCursor(more.next_cursor ?? undefined);
    } finally {
      setLoadingMore(false);
    }
  }, [cursor, topicFilter, difficultyFilter]);

  if (isLoading) return <LoadingSpinner text="Loading training modules..." />;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Training Modules</h1>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          Create Module
        </Button>
      </div>

      <FilterBar>
        <FilterSelect
          label="All Difficulties"
          value={difficultyFilter}
          options={DIFFICULTY_OPTIONS}
          onChange={setDifficultyFilter}
        />
        <input
          type="text"
          value={topicFilter}
          onChange={(e) => setTopicFilter(e.target.value)}
          placeholder="Filter by topic..."
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </FilterBar>

      {modules.length === 0 ? (
        <EmptyState
          message={
            topicFilter || difficultyFilter
              ? "No modules match your filters"
              : "No training modules created yet"
          }
          actionLabel={topicFilter || difficultyFilter ? "Clear filters" : undefined}
          onAction={
            topicFilter || difficultyFilter
              ? () => {
                  setTopicFilter("");
                  setDifficultyFilter("");
                }
              : undefined
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {modules.map((m) => (
              <button
                key={m.id}
                onClick={() => setSelectedId(m.id)}
                className="text-left"
              >
                <Card className="h-full transition-shadow hover:shadow-md">
                  <div className="flex items-start justify-between">
                    <h3 className="font-semibold text-gray-900">{m.title}</h3>
                    <Badge variant={m.is_active ? "success" : "default"}>
                      {m.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <div className="mt-2 flex gap-2">
                    <Badge variant="info">{m.topic}</Badge>
                    <Badge variant={DIFFICULTY_VARIANT[m.difficulty] ?? "default"}>
                      {m.difficulty}
                    </Badge>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-2 text-center">
                    <div>
                      <p className="text-lg font-bold text-gray-900">{m.duration_minutes}m</p>
                      <p className="text-xs text-gray-500">Duration</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold text-gray-900">{m.times_assigned}</p>
                      <p className="text-xs text-gray-500">Assigned</p>
                    </div>
                  </div>
                </Card>
              </button>
            ))}
          </div>
          {cursor && (
            <div className="flex justify-center">
              <Button variant="secondary" onClick={loadMore} loading={loadingMore}>
                Load More
              </Button>
            </div>
          )}
        </>
      )}

      {selectedId && (
        <ModuleDetail
          moduleId={selectedId}
          onClose={() => setSelectedId(null)}
          onRefreshList={refetch}
        />
      )}

      <CreateModuleModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={refetch}
      />
    </div>
  );
}
