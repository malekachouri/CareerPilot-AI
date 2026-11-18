"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, Card, PageHeader, ProvenanceBadge, btn } from "@/components/ui";
import { api, problemMessage } from "@/lib/api/client";
import { DIFFICULTY_LABELS, TYPE_LABELS, type TestSummary } from "@/lib/api/types";

export function TestDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [test, setTest] = useState<TestSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    api.GET("/api/v1/tests/{test_id}", { params: { path: { test_id: id } } }).then(({ data, error }) => {
      if (data) setTest(data);
      else setError(problemMessage(error, "Test not found"));
    });
  }, [id]);

  async function start() {
    setStarting(true);
    const res = await api.POST("/api/v1/tests/{test_id}/attempts", { params: { path: { test_id: id } } });
    if (res.error || !res.data) {
      setStarting(false);
      return setError(problemMessage(res.error));
    }
    router.push(`/attempts/${(res.data as { id: string }).id}`);
  }

  async function remove() {
    if (!confirm("Delete this test? Attempts are deleted too.")) return;
    await api.DELETE("/api/v1/tests/{test_id}", { params: { path: { test_id: id } } });
    router.push("/tests");
  }

  if (error) return <p role="alert" className="text-danger">{error}</p>;
  if (!test) return <p className="text-muted">Loading…</p>;

  return (
    <div className="space-y-6">
      <PageHeader title={test.title} back={{ href: "/tests", label: "Test library" }}>
        {test.description}
      </PageHeader>
      {test.label && <p className="rounded-md border border-border bg-surface px-3 py-2 text-sm">{test.label}</p>}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-xs uppercase text-muted">Questions</p>
          <p className="text-2xl font-semibold">{test.question_count}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-muted">Time limit</p>
          <p className="text-2xl font-semibold">{test.time_limit_s ? `${Math.round(test.time_limit_s / 60)} min` : "Untimed"}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-muted">Average level</p>
          <p className="text-2xl font-semibold">{test.average_difficulty ? DIFFICULTY_LABELS[Math.round(test.average_difficulty)] : "–"}</p>
        </Card>
      </div>
      <Card className="space-y-3 text-sm">
        <div className="flex flex-wrap gap-1">
          {test.categories.map((c) => (
            <Badge key={c.slug}>{c.name}</Badge>
          ))}
        </div>
        <p className="text-muted">Formats: {test.types.map((t) => TYPE_LABELS[t] ?? t).join(", ")}</p>
        <div className="flex flex-wrap gap-1">
          {test.provenance.map((p) => (
            <ProvenanceBadge key={p} provenance={p} />
          ))}
        </div>
        <p className="text-muted">
          {test.mode === "practice" ? "Practice mode" : "Exam mode"}. Your answers are saved as you go: you can reload the page
          and continue. {test.time_limit_s ? "The timer runs on the server and the test is submitted automatically when it ends." : ""}
        </p>
      </Card>
      <div className="flex gap-3">
        <button className={btn.primary} onClick={start} disabled={starting || test.question_count === 0}>
          {starting ? "Starting…" : "Start test"}
        </button>
        {test.is_mine && (
          <button className={btn.secondary} onClick={remove}>
            Delete
          </button>
        )}
      </div>
    </div>
  );
}
