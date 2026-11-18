"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge, ProvenanceBadge, btn, input } from "@/components/ui";
import { api, problemMessage } from "@/lib/api/client";
import { DIFFICULTY_LABELS, TYPE_LABELS, type AttemptQuestion, type AttemptState } from "@/lib/api/types";

const MULTI = new Set(["mcq_multi"]);
const TEXT = new Set(["open_ended", "coding", "debugging", "simulation"]);

function formatClock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function AttemptPlayer() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [state, setState] = useState<AttemptState | null>(null);
  const [current, setCurrent] = useState(0);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const deadline = useRef<number | null>(null);
  const enteredAt = useRef<number>(Date.now());
  const submitted = useRef(false);

  useEffect(() => {
    api.GET("/api/v1/attempts/{attempt_id}", { params: { path: { attempt_id: id } } }).then(({ data, error }) => {
      if (!data) return setError(problemMessage(error, "Attempt not found"));
      const s = data as unknown as AttemptState;
      if (s.status === "submitted") return router.replace(`/attempts/${id}/results`);
      setState(s);
      // The server is the clock: convert its remaining time into a local deadline.
      if (s.remaining_seconds !== null) deadline.current = Date.now() + s.remaining_seconds * 1000;
      const firstOpen = s.questions.findIndex((q) => !q.answered);
      setCurrent(firstOpen >= 0 ? firstOpen : 0);
    });
  }, [id, router]);

  const submit = useCallback(
    async (auto = false) => {
      if (submitted.current) return;
      submitted.current = true;
      setSubmitting(true);
      const { error } = await api.POST("/api/v1/attempts/{attempt_id}/submit", { params: { path: { attempt_id: id } } });
      if (error && !auto) {
        submitted.current = false;
        setSubmitting(false);
        return setError(problemMessage(error));
      }
      router.replace(`/attempts/${id}/results`);
    },
    [id, router],
  );

  useEffect(() => {
    if (deadline.current === null) return;
    const tick = () => {
      const left = Math.max(0, Math.round(((deadline.current ?? 0) - Date.now()) / 1000));
      setRemaining(left);
      if (left === 0) void submit(true);
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [state?.id, submit]);

  const save = useCallback(
    async (position: number, patch: { selected?: string[]; text_answer?: string; flagged?: boolean }) => {
      const spent = Date.now() - enteredAt.current;
      enteredAt.current = Date.now();
      setState((s) =>
        s && {
          ...s,
          questions: s.questions.map((q) =>
            q.position === position
              ? { ...q, ...patch, answered: (patch.selected ?? q.selected ?? []).length > 0 || Boolean(patch.text_answer ?? q.text_answer) }
              : q,
          ),
        },
      );
      setSaving(true);
      const { error } = await api.PUT("/api/v1/attempts/{attempt_id}/answers/{position}", {
        params: { path: { attempt_id: id, position } },
        body: { ...patch, time_spent_ms: Math.min(spent, 3_600_000) },
      });
      setSaving(false);
      if (error) {
        const p = error as { status?: number };
        if (p.status === 409) return router.replace(`/attempts/${id}/results`);
        setError(problemMessage(error));
      }
    },
    [id, router],
  );

  const go = useCallback(
    (index: number) => {
      if (!state) return;
      setCurrent(Math.max(0, Math.min(state.questions.length - 1, index)));
      enteredAt.current = Date.now();
    },
    [state],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!state || (e.target as HTMLElement).closest("textarea, input, select")) return;
      if (e.key === "ArrowRight") go(current + 1);
      if (e.key === "ArrowLeft") go(current - 1);
      const q = state.questions[current];
      const idx = Number(e.key) - 1;
      if (q && idx >= 0 && idx < q.question.options.length) choose(q, q.question.options[idx].id);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function choose(q: AttemptQuestion, optionId: string) {
    const prev = q.selected ?? [];
    const next = MULTI.has(q.question.type)
      ? prev.includes(optionId)
        ? prev.filter((x) => x !== optionId)
        : [...prev, optionId]
      : [optionId];
    void save(q.position, { selected: next });
  }

  if (error) return <p role="alert" className="text-danger">{error}</p>;
  if (!state) return <p className="text-muted">Loading the test…</p>;

  const q = state.questions[current];
  const answered = state.questions.filter((x) => x.answered).length;
  const lowTime = remaining !== null && remaining <= 60;

  return (
    <div className="space-y-6">
      <div className="sticky top-0 z-10 -mx-4 flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background/95 px-4 py-3 backdrop-blur">
        <div>
          <p className="font-semibold">{state.test?.title}</p>
          <p className="text-xs text-muted">
            {answered}/{state.questions.length} answered {saving ? "· saving…" : "· saved"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {remaining !== null && (
            <span
              role="timer"
              aria-live={lowTime ? "assertive" : "off"}
              className={`rounded-md border px-3 py-1 font-mono text-lg tabular-nums ${lowTime ? "border-critical text-critical" : "border-border"}`}
            >
              {lowTime && "⚠ "}
              {formatClock(remaining)}
            </span>
          )}
          <button
            className={btn.primary}
            disabled={submitting}
            onClick={() => {
              const open = state.questions.length - answered;
              if (confirm(open ? `${open} question(s) unanswered. Submit anyway?` : "Submit your answers?")) void submit();
            }}
          >
            {submitting ? "Submitting…" : "Submit"}
          </button>
        </div>
      </div>

      <nav aria-label="Questions" className="flex flex-wrap gap-1.5">
        {state.questions.map((x, i) => (
          <button
            key={x.position}
            onClick={() => go(i)}
            aria-current={i === current ? "step" : undefined}
            aria-label={`Question ${i + 1}${x.answered ? ", answered" : ""}${x.flagged ? ", flagged" : ""}`}
            className={`relative h-9 w-9 rounded-md border text-sm tabular-nums ${
              i === current ? "border-accent ring-2 ring-accent/40" : "border-border"
            } ${x.answered ? "bg-accent/15 font-semibold" : "bg-surface"}`}
          >
            {i + 1}
            {x.flagged && <span className="absolute -right-1 -top-1 text-xs" aria-hidden>⚑</span>}
          </button>
        ))}
      </nav>

      <article className="space-y-4 rounded-lg border border-border bg-surface p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <span>Question {current + 1} of {state.questions.length}</span>
          <Badge>{TYPE_LABELS[q.question.type] ?? q.question.type}</Badge>
          <Badge>{DIFFICULTY_LABELS[q.question.difficulty]}</Badge>
          {q.question.categories.map((c) => (
            <Badge key={c.slug}>{c.name}</Badge>
          ))}
          <ProvenanceBadge provenance={q.question.provenance} />
        </div>
        {q.question.label && <p className="text-xs text-muted">{q.question.label}</p>}
        {q.question.context && (
          <pre className="whitespace-pre-wrap rounded-md border border-border bg-background p-3 font-sans text-sm">{q.question.context}</pre>
        )}
        <h2 className="text-lg font-medium leading-snug">{q.question.stem}</h2>
        {MULTI.has(q.question.type) && <p className="text-sm text-muted">Select all that apply.</p>}

        {q.question.options.length > 0 ? (
          <fieldset className="space-y-2">
            <legend className="sr-only">Answer options</legend>
            {q.question.options.map((o, i) => {
              const checked = (q.selected ?? []).includes(o.id);
              return (
                <label
                  key={o.id}
                  className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 text-sm ${checked ? "border-accent bg-accent/10" : "border-border hover:border-accent/60"}`}
                >
                  <input
                    type={MULTI.has(q.question.type) ? "checkbox" : "radio"}
                    name={`q-${q.position}`}
                    checked={checked}
                    onChange={() => choose(q, o.id)}
                    className="mt-0.5"
                  />
                  <span className="w-5 shrink-0 font-mono text-muted">{i + 1}.</span>
                  <span className="whitespace-pre-wrap">{o.text}</span>
                </label>
              );
            })}
          </fieldset>
        ) : (
          TEXT.has(q.question.type) && (
            <textarea
              aria-label="Your answer"
              className={`${input} min-h-40 font-mono`}
              defaultValue={q.text_answer ?? ""}
              key={q.position}
              onBlur={(e) => e.target.value !== (q.text_answer ?? "") && save(q.position, { text_answer: e.target.value })}
              placeholder="Write your answer. You will compare it with the explanation after submitting."
            />
          )
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
          <button className={btn.ghost} onClick={() => save(q.position, { flagged: !q.flagged })} aria-pressed={q.flagged}>
            {q.flagged ? "⚑ Flagged for review" : "⚐ Flag for review"}
          </button>
          <div className="flex gap-2">
            <button className={btn.secondary} onClick={() => go(current - 1)} disabled={current === 0}>
              ← Previous
            </button>
            <button className={btn.secondary} onClick={() => go(current + 1)} disabled={current === state.questions.length - 1}>
              Next →
            </button>
          </div>
        </div>
      </article>
      <p className="text-xs text-muted">Keyboard: ← → to move, 1–6 to choose an option.</p>
    </div>
  );
}
