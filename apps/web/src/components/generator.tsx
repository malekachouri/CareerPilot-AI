"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { CategorySelect } from "@/components/tests-library";
import { Card, btn, input } from "@/components/ui";
import { api, problemMessage } from "@/lib/api/client";
import { DIFFICULTY_LABELS, TYPE_LABELS, type Category, type GeneratorStatus, type Job } from "@/lib/api/types";

export function Generator() {
  const [status, setStatus] = useState<GeneratorStatus | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState({ position: "DevOps Engineer", category: "kubernetes", difficulty: 2, count: 5, duration: 10, type: "mcq_single" });
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.GET("/api/v1/generator/status").then(({ data }) => setStatus(data as unknown as GeneratorStatus));
    api.GET("/api/v1/categories").then(({ data }) => setCategories(data ?? []));
    return () => {
      if (poll.current) clearInterval(poll.current);
    };
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const { data, error } = await api.POST("/api/v1/generator/questions", {
      body: {
        position: form.position,
        category: form.category,
        difficulty: form.difficulty,
        count: form.count,
        duration_minutes: form.duration || null,
        question_type: form.type as "mcq_single",
        language: "en",
        self_check: true,
      },
    });
    if (error || !data) return setError(problemMessage(error));
    setJob(data);
    poll.current = setInterval(async () => {
      const r = await api.GET("/api/v1/jobs/{job_id}", { params: { path: { job_id: data.id } } });
      if (r.data) {
        setJob(r.data);
        if (r.data.status === "succeeded" || r.data.status === "failed") clearInterval(poll.current!);
      }
    }, 3000);
  }

  const result = job?.result as { created?: number; invalid?: number; failed_self_check?: number; duplicates?: number; test_id?: string | null } | undefined;
  const running = job && (job.status === "queued" || job.status === "running");

  return (
    <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-sm">
              <span className="font-medium">Position</span>
              <input className={input} value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} required minLength={2} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium">Technology</span>
              <CategorySelect categories={categories} allowGroups={false} value={form.category} onChange={(v) => setForm({ ...form, category: v })} label="Choose a topic" />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium">Level</span>
              <select className={input} value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: Number(e.target.value) })}>
                {Object.entries(DIFFICULTY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium">Question type</span>
              <select className={input} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                {(status?.types ?? ["mcq_single"]).map((t) => <option key={t} value={t}>{TYPE_LABELS[t] ?? t}</option>)}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium">Number of questions</span>
              <input type="number" min={1} max={20} className={input} value={form.count} onChange={(e) => setForm({ ...form, count: Number(e.target.value) })} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium">Duration (minutes, 0 = untimed)</span>
              <input type="number" min={0} max={240} className={input} value={form.duration} onChange={(e) => setForm({ ...form, duration: Number(e.target.value) })} />
            </label>
          </div>
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
          <button className={btn.primary} disabled={!status?.available || Boolean(running) || !form.category}>
            {running ? "Generating…" : "Generate questions"}
          </button>
        </form>
      </Card>

      <div className="space-y-4">
        <Card className="text-sm">
          <p className="font-medium">Local model</p>
          {status === null ? (
            <p className="text-muted">Checking…</p>
          ) : status.available ? (
            <p className="text-good">✓ {status.provider} · {status.model} is ready</p>
          ) : (
            <div className="space-y-1 text-muted">
              <p className="text-critical">✗ {status.provider} · {status.model} is not available</p>
              <p>
                Start the AI profile and pull the model: <code className="font-mono">docker compose --profile ai up -d</code> then{" "}
                <code className="font-mono">docker compose exec ollama ollama pull {status.model}</code>
              </p>
            </div>
          )}
        </Card>
        <Card className="text-sm text-muted">
          Generated questions are <strong>AI-generated and unverified</strong>. Each draft is checked: valid key, no duplicates,
          and a second blind pass where the model must find its own answer. They stay private to you and are kept apart
          from verified questions.
        </Card>
        {job && (
          <Card className="text-sm" >
            <p className="font-medium" role="status">Job: {job.status}</p>
            {running && <p className="text-muted">A local model can take a few minutes on a CPU. Keep this page open.</p>}
            {job.status === "failed" && <p className="text-critical">✗ {job.error}</p>}
            {job.status === "succeeded" && result && (
              <div className="space-y-2">
                <p>✓ {result.created} question(s) created · {result.invalid ?? 0} invalid · {result.failed_self_check ?? 0} failed the self-check · {result.duplicates ?? 0} duplicate(s)</p>
                {result.test_id && <Link className={btn.primary} href={`/tests/${result.test_id}`}>Open the generated test</Link>}
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
