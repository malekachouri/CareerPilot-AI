"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { BarList, Badge, Card, PageHeader, ProvenanceBadge, Stat, Verdict, btn, formatDuration, input } from "@/components/ui";
import { api, problemMessage } from "@/lib/api/client";
import { DIFFICULTY_LABELS, type AttemptResults, type ResultItem } from "@/lib/api/types";

export function AttemptResultsView() {
  const { id } = useParams<{ id: string }>();
  const [res, setRes] = useState<AttemptResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "wrong" | "ungraded">("all");

  const load = useCallback(() => {
    api.GET("/api/v1/attempts/{attempt_id}/results", { params: { path: { attempt_id: id } } }).then(({ data, error }) => {
      if (data) setRes(data as unknown as AttemptResults);
      else setError(problemMessage(error));
    });
  }, [id]);
  useEffect(load, [load]);

  if (error) return <p role="alert" className="text-danger">{error}</p>;
  if (!res) return <p className="text-muted">Loading results…</p>;

  const items = res.items.filter((i) => (filter === "wrong" ? i.is_correct === false : filter === "ungraded" ? i.is_correct === null : true));

  return (
    <div className="space-y-8">
      <PageHeader title={`Results · ${res.test?.title ?? ""}`} back={{ href: "/tests", label: "Test library" }}>
        {res.auto_submitted ? "Time ran out: the test was submitted automatically." : "Submitted."} Duration {formatDuration((res.duration_s ?? 0) * 1000)}.
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Score" value={res.percent !== null ? `${res.percent}%` : "–"} hint={res.max_score ? `${res.score} / ${res.max_score} points` : "Nothing auto-graded"} />
        <Stat label="Correct" value={`✓ ${res.correct}`} />
        <Stat label="Incorrect" value={`✗ ${res.incorrect}`} hint={res.unanswered ? `${res.unanswered} unanswered` : undefined} />
        <Stat label="Avg. time / question" value={formatDuration(res.average_time_ms)} hint={res.ungraded ? `${res.ungraded} not auto-graded` : undefined} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-semibold">Accuracy by topic</h2>
          <BarList rows={res.by_category.map((c) => ({ key: c.slug, label: c.name, value: c.accuracy, detail: `${c.correct}/${c.answered} correct` }))} />
        </Card>
        <Card>
          <h2 className="mb-3 font-semibold">Accuracy by level</h2>
          <BarList rows={res.by_difficulty.map((d) => ({ key: String(d.difficulty), label: DIFFICULTY_LABELS[d.difficulty], value: d.accuracy, detail: `${d.correct}/${d.answered} correct` }))} />
        </Card>
      </div>

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Review & explanations</h2>
          <div className="flex gap-1 text-sm" role="tablist">
            {(["all", "wrong", "ungraded"] as const).map((f) => (
              <button key={f} role="tab" aria-selected={filter === f} onClick={() => setFilter(f)} className={`rounded-md px-3 py-1 ${filter === f ? "bg-accent text-accent-foreground" : "border border-border"}`}>
                {f === "all" ? "All" : f === "wrong" ? "Incorrect" : "Not graded"}
              </button>
            ))}
          </div>
        </div>
        {items.map((item) => (
          <ReviewItem key={item.position} item={item} attemptId={id} onChange={load} />
        ))}
        {items.length === 0 && <p className="text-sm text-muted">Nothing here.</p>}
      </section>

      <div className="flex gap-3">
        {res.test && (
          <Link href={`/tests/${res.test.id}`} className={btn.secondary}>
            Retake
          </Link>
        )}
        <Link href="/analytics" className={btn.secondary}>
          My progress
        </Link>
      </div>
    </div>
  );
}

function ReviewItem({ item, attemptId, onChange }: { item: ResultItem; attemptId: string; onChange: () => void }) {
  const q = item.question;
  const key = new Set(q.answer_key ?? []);
  const chosen = new Set(item.selected ?? []);
  const [newKey, setNewKey] = useState<string[]>([]);
  const isPrivate = q.visibility === "private";

  async function selfGrade(correct: boolean) {
    await api.POST("/api/v1/attempts/{attempt_id}/answers/{position}/self-grade", {
      params: { path: { attempt_id: attemptId, position: item.position } },
      body: { correct },
    });
    onChange();
  }

  async function saveKey() {
    if (!newKey.length) return;
    await api.PUT("/api/v1/questions/{question_id}/answer-key", { params: { path: { question_id: q.id } }, body: { answer: newKey } });
    onChange();
  }

  return (
    <article className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted">
          Question {item.position + 1} · {DIFFICULTY_LABELS[q.difficulty]} · {formatDuration(item.time_spent_ms)}
        </p>
        <Verdict value={item.is_correct} />
      </div>
      {q.context && <pre className="whitespace-pre-wrap rounded-md border border-border bg-background p-3 font-sans text-sm">{q.context}</pre>}
      <p className="font-medium">{q.stem}</p>
      {q.options.length > 0 && (
        <ul className="space-y-1.5 text-sm" role="list">
          {q.options.map((o) => {
            const isKey = key.has(o.id);
            const isChosen = chosen.has(o.id);
            return (
              <li key={o.id} className={`rounded-md border p-2 ${isKey ? "border-good" : isChosen ? "border-critical" : "border-border"}`}>
                <div className="flex gap-2">
                  <span className="w-28 shrink-0 text-xs font-medium">
                    {isKey && <span className="text-good">✓ Correct</span>}
                    {isChosen && !isKey && <span className="text-critical">✗ Your answer</span>}
                    {isChosen && isKey && <span className="text-muted"> · yours</span>}
                  </span>
                  <span className="whitespace-pre-wrap">{o.text}</span>
                </div>
                {q.distractor_explanations?.[o.id] && <p className="mt-1 text-xs text-muted sm:pl-30">{q.distractor_explanations[o.id]}</p>}
              </li>
            );
          })}
        </ul>
      )}
      {item.text_answer && (
        <div className="text-sm">
          <p className="text-xs font-medium text-muted">Your answer</p>
          <pre className="whitespace-pre-wrap rounded-md border border-border bg-background p-2 font-sans">{item.text_answer}</pre>
        </div>
      )}
      {q.explanation ? (
        <div className="rounded-md bg-background p-3 text-sm">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Explanation</p>
          <p className="whitespace-pre-wrap">{q.explanation}</p>
        </div>
      ) : (
        !q.answer_key && <p className="text-sm text-muted">No answer key for this question yet.</p>
      )}

      {item.graded_by !== "key" && (q.type === "open_ended" || q.type === "coding" || q.type === "debugging" || !q.answer_key) && q.type !== "survey" && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Grade yourself:</span>
          <button className={btn.secondary} onClick={() => selfGrade(true)} aria-pressed={item.graded_by === "self" && item.is_correct === true}>✓ I got it right</button>
          <button className={btn.secondary} onClick={() => selfGrade(false)} aria-pressed={item.graded_by === "self" && item.is_correct === false}>✗ I got it wrong</button>
        </div>
      )}

      {isPrivate && !q.answer_key && q.options.length > 0 && q.type !== "survey" && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-dashed border-border p-3 text-sm">
          <span>Set the correct answer you confirmed:</span>
          <select multiple={q.type === "mcq_multi"} aria-label="Correct option" className={`${input} w-auto`} onChange={(e) => setNewKey(Array.from(e.target.selectedOptions).map((o) => o.value))}>
            {q.type !== "mcq_multi" && <option value="">Choose…</option>}
            {q.options.map((o, i) => (
              <option key={o.id} value={o.id}>
                {i + 1}. {o.text.slice(0, 60)}
              </option>
            ))}
          </select>
          <button className={btn.secondary} onClick={saveKey}>Save key</button>
        </div>
      )}

      <div className="flex flex-wrap gap-1 border-t border-border pt-2 text-xs text-muted">
        <ProvenanceBadge provenance={q.provenance} />
        {q.categories.map((c) => (
          <Badge key={c.slug}>{c.name}</Badge>
        ))}
        {q.source && (
          <span>
            Source:{" "}
            {q.source.url ? (
              <a href={q.source_ref?.startsWith("http") ? q.source_ref : q.source.url} className="underline" target="_blank" rel="noreferrer noopener">
                {q.source.name}
              </a>
            ) : (
              q.source.name
            )}
            {q.source.license_spdx && ` · ${q.source.license_spdx}`}
            {q.source.attribution && ` · ${q.source.attribution}`}
          </span>
        )}
      </div>
    </article>
  );
}
