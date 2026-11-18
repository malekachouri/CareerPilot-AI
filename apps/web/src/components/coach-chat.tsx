"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { CODE_LANGUAGES, type CodeLanguage } from "@/components/code-editor";
import { Badge, BarList, ProvenanceBadge, Stat, Verdict, btn, input } from "@/components/ui";
import { coach } from "@/lib/api/coach";
import type { CoachMessage, CoachSession, Reference } from "@/lib/api/coach-types";

const CodeEditor = dynamic(() => import("@/components/code-editor"), { ssr: false, loading: () => <p className="text-sm text-muted">Loading editor…</p> });

export function CoachChat() {
  const { id } = useParams<{ id: string }>();
  const [s, setS] = useState<CoachSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const count = useRef(0);

  const load = useCallback(async () => {
    const { data, error } = await coach<CoachSession>(`/coach/sessions/${id}`);
    if (data) setS(data);
    else setError(error ?? "Session not found");
  }, [id]);

  useEffect(() => {
    coach<CoachSession>(`/coach/sessions/${id}`).then(({ data, error }) => {
      if (data) setS(data);
      else setError(error ?? "Session not found");
    });
  }, [id]);

  // Poll while the coach (local model, in a background job) is working.
  const working = Boolean(s && (s.state.pending || s.messages.some((m) => m.status === "pending")));
  useEffect(() => {
    if (!working) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [working, load]);

  useEffect(() => {
    if (s && s.messages.length !== count.current) {
      count.current = s.messages.length;
      bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [s]);

  async function act(path: string, body?: unknown) {
    setSending(true);
    setError(null);
    const { data, error } = await coach<CoachSession>(`/coach/sessions/${id}${path}`, { method: "POST", body });
    setSending(false);
    if (data) setS(data);
    if (error) setError(error);
  }

  if (!s) return error ? <p role="alert" className="text-danger">{error}</p> : <p className="text-muted">Loading…</p>;

  const current = s.state.current ? s.messages.find((m) => m.id === s.state.current?.message_id) : undefined;
  const interview = s.kind === "interview";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/coach" className="text-sm text-muted hover:text-foreground">← Coach</Link>
          <h1 className="text-xl font-bold">{s.title}</h1>
          <p className="text-xs text-muted">
            {s.agent.name}
            {s.learning_mode && " · learning mode"}
            {s.state.interview && ` · question ${Math.max(1, s.state.interview.main_asked)} of ${s.state.interview.total}`}
            {s.status === "ended" && " · ended"}
          </p>
        </div>
        {s.status === "active" && (
          <button className={btn.secondary} onClick={() => act("/end")} disabled={sending || working}>
            {interview ? "End interview & get report" : "End session"}
          </button>
        )}
      </div>

      <ol className="space-y-3" aria-live="polite">
        {s.messages.map((m) => (
          <li key={m.id}>
            <Message m={m} onRetry={() => act(`/messages/${m.id}/retry`)} />
          </li>
        ))}
      </ol>
      <div ref={bottom} />

      {error && <p role="alert" className="text-sm text-danger">{error}</p>}

      {s.status === "active" && (
        <div className="sticky bottom-0 -mx-4 space-y-3 border-t border-border bg-background/95 px-4 py-3 backdrop-blur">
          {interview ? (
            s.state.interview?.awaiting_answer && <TextAnswer disabled={sending} onSubmit={(text) => act("/answer", { text })} placeholder="Answer as you would in the interview…" />
          ) : s.state.step === "awaiting_answer" && current ? (
            <AnswerBox message={current} session={s} disabled={sending || working} onAnswer={(body) => act("/answer", body)} onHint={() => act("/hint")} onReveal={() => act("/reveal")} />
          ) : s.state.step === "evaluated" && !working ? (
            <div className="flex flex-wrap gap-2">
              <button className={btn.primary} onClick={() => act("/next")} disabled={sending}>Next question →</button>
              <button className={btn.secondary} onClick={() => act("/similar")} disabled={sending}>Similar exercise</button>
            </div>
          ) : null}
          {!interview && <AskTutor disabled={sending || working} onAsk={(message) => act("/ask", { message })} />}
          {working && <p className="text-xs text-muted" role="status">The coach is thinking… a local model can take up to a minute.</p>}
        </div>
      )}
    </div>
  );
}

// --- messages ------------------------------------------------------------------------------------------

function Message({ m, onRetry }: { m: CoachMessage; onRetry: () => void }) {
  if (m.status === "pending")
    return <Bubble role="coach"><p className="animate-pulse text-sm text-muted">{pendingLabel(m.kind)}</p></Bubble>;
  if (m.status === "failed")
    return (
      <Bubble role="coach">
        <p className="text-sm text-critical">✗ {m.content}</p>
        <button className={`${btn.ghost} mt-1`} onClick={onRetry}>↻ Retry</button>
      </Bubble>
    );
  switch (m.kind) {
    case "notice":
      return <p className="whitespace-pre-wrap rounded-md border border-border bg-surface px-3 py-2 text-sm text-muted">{m.content}</p>;
    case "question":
      return <QuestionCard m={m} />;
    case "answer":
      return <UserAnswer m={m} />;
    case "evaluation":
      return <Evaluation m={m} />;
    case "insight":
      return <Insight m={m} />;
    case "recommendation":
      return <Recommendation m={m} />;
    case "hint":
      return <Bubble role="coach"><p className="text-sm">💡 <span className="font-medium">Hint {m.data.level}/3:</span> {m.content}</p></Bubble>;
    case "chat":
      return (
        <Bubble role={m.role}>
          <p className="whitespace-pre-wrap text-sm">{m.content}</p>
          <References refs={m.data.references} />
        </Bubble>
      );
    case "report":
      return <Report m={m} />;
    default:
      return null;
  }
}

function pendingLabel(kind: string) {
  return { question: "Preparing the next question…", evaluation: "Evaluating your answer…", insight: "Writing a detailed explanation…", hint: "Thinking of a hint…", chat: "Looking it up…", report: "Writing your interview report…" }[kind] ?? "Working…";
}

function Bubble({ role, children }: { role: string; children: React.ReactNode }) {
  return (
    <div className={`flex ${role === "user" ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[92%] rounded-lg border px-4 py-3 ${role === "user" ? "border-accent/40 bg-accent/10" : "border-border bg-surface"}`}>{children}</div>
    </div>
  );
}

function QuestionCard({ m }: { m: CoachMessage }) {
  const d = m.data;
  if (d.interview)
    return (
      <Bubble role="coach">
        <p className="mb-1 text-xs text-muted">
          {d.follow_up ? "Follow-up" : `Question ${d.number} of ${d.total}`}
          {d.competency && ` · ${d.competency}`}
        </p>
        {d.context && <p className="mb-1 whitespace-pre-wrap text-sm text-muted">{d.context}</p>}
        <p className="whitespace-pre-wrap font-medium">{m.content}</p>
      </Bubble>
    );
  const q = d.question ?? {};
  return (
    <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        {(d.skills ?? []).map((sk: { slug: string; name: string }) => <Badge key={sk.slug}>{sk.name}</Badge>)}
        <Badge>{d.difficulty_label}</Badge>
        <span>⏱ recommended {Math.round((d.recommended_time_s ?? 90) / 60) || 1} min</span>
        {d.provenance && <ProvenanceBadge provenance={d.provenance} />}
        {d.selection?.reason && <span>· {d.selection.reason}</span>}
      </div>
      {d.label && <p className="text-xs text-muted">{d.label}</p>}
      {q.context && <pre className="whitespace-pre-wrap rounded-md border border-border bg-background p-3 font-sans text-sm">{q.context}</pre>}
      <p className="text-lg font-medium leading-snug">{q.stem}</p>
      {q.options?.length > 0 && (
        <ol className="space-y-1 text-sm">
          {q.options.map((o: { id: string; text: string }, i: number) => (
            <li key={o.id} className="flex gap-2"><span className="w-5 font-mono text-muted">{"ABCDEFGH"[i]}.</span><span className="whitespace-pre-wrap">{o.text}</span></li>
          ))}
        </ol>
      )}
      {d.source && <p className="text-xs text-muted">Source: {d.source.name}{d.source.license && ` · ${d.source.license}`}</p>}
    </div>
  );
}

function UserAnswer({ m }: { m: CoachMessage }) {
  const code = m.data.language;
  return (
    <Bubble role="user">
      {code ? <pre className="overflow-x-auto font-mono text-xs">{m.data.text}</pre> : <p className="whitespace-pre-wrap text-sm">{m.data.selected?.length ? `Selected: ${m.data.selected.join(", ")}` : (m.data.text ?? m.content)}</p>}
    </Bubble>
  );
}

function Evaluation({ m }: { m: CoachMessage }) {
  const d = m.data;
  if (d.reflection)
    return <Bubble role="coach"><p className="text-sm">{m.content}</p><p className="mt-2 text-xs text-muted">{d.disclaimer}</p></Bubble>;
  if (d.criteria) {
    return (
      <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-semibold">Feedback</p>
          <span className="text-sm font-medium tabular-nums">{d.score}/100 · {d.verdict}</span>
        </div>
        <BarList rows={d.criteria.map((c: { key: string; label: string; score: number }) => ({ key: c.key, label: c.label, value: c.score / 5 }))} format={(v) => `${Math.round(v * 5)}/5`} />
        <p className="whitespace-pre-wrap text-sm">{d.feedback}</p>
        <TwoLists a={["Strengths", d.strengths]} b={["To improve", d.improvements]} />
        {d.executed === false && (
          <div className="space-y-2 rounded-md bg-background p-3 text-sm">
            <p className="text-xs text-muted">Code reviewed by reasoning, not executed (the sandbox comes in phase 4).</p>
            <p>Complexity: time <code className="font-mono">{d.complexity?.time}</code>, space <code className="font-mono">{d.complexity?.space}</code></p>
            {d.traced_examples && <p className="whitespace-pre-wrap text-muted">{d.traced_examples}</p>}
            {d.issues?.length > 0 && <ul className="list-disc pl-5">{d.issues.map((i: string) => <li key={i}>{i}</li>)}</ul>}
            {d.optimized_solution && <details><summary className="cursor-pointer font-medium">Optimised solution</summary><pre className="mt-2 overflow-x-auto font-mono text-xs">{d.optimized_solution}</pre></details>}
          </div>
        )}
        {d.model_answer && <details className="text-sm"><summary className="cursor-pointer font-medium">Model answer</summary><p className="mt-2 whitespace-pre-wrap">{d.model_answer}</p></details>}
        <Teaching d={d} />
        <References refs={d.references} />
      </div>
    );
  }
  return (
    <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {d.revealed ? <p className="font-semibold">Answer (learning mode)</p> : <Verdict value={d.is_correct} />}
        {d.score !== null && d.score !== undefined && !d.revealed && <span className="text-sm tabular-nums">Score {d.score}/100</span>}
      </div>
      {d.correct_options?.length > 0 && (
        <p className="text-sm"><span className="font-medium text-good">✓ Correct answer:</span> {d.correct_options.map((o: { id: string; text: string }) => o.text).join(" · ")}</p>
      )}
      {d.explanation && <p className="whitespace-pre-wrap text-sm">{d.explanation}</p>}
      {Object.keys(d.why_wrong ?? {}).length > 0 && (
        <div className="text-sm">
          <p className="font-medium">Why the other options are wrong</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {Object.entries(d.why_wrong as Record<string, string>).map(([id, why]) => (
              <li key={id}><span className={(d.selected ?? []).includes(id) ? "font-medium text-critical" : ""}>{(d.selected ?? []).includes(id) && "✗ your choice · "}</span>{why}</li>
            ))}
          </ul>
        </div>
      )}
      {m.content && !d.explanation && <p className="text-sm text-muted">{m.content}</p>}
    </div>
  );
}

function Insight({ m }: { m: CoachMessage }) {
  const d = m.data;
  if (d.discarded) return <p className="text-xs text-muted">{m.content}</p>;
  return (
    <div className="space-y-3 rounded-lg border border-border bg-surface p-4 text-sm">
      <p className="font-semibold">Step by step</p>
      {d.reasoning_steps?.length > 0 && <ol className="list-decimal space-y-1 pl-5">{d.reasoning_steps.map((s: string, i: number) => <li key={i}>{s}</li>)}</ol>}
      {Object.keys(d.why_wrong ?? {}).length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-muted">{Object.entries(d.why_wrong as Record<string, string>).map(([id, w]) => <li key={id}>{w}</li>)}</ul>
      )}
      <Teaching d={d} />
      <References refs={d.references} />
      <p className="text-xs text-muted">AI explanation, checked against the answer key. It may still contain errors.</p>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function Teaching({ d }: { d: Record<string, any> }) {
  return (
    <>
      {d.concepts?.length > 0 && <div className="flex flex-wrap gap-1">{d.concepts.map((c: string) => <Badge key={c}>{c}</Badge>)}</div>}
      {d.real_world_example && <p className="text-sm"><span className="font-medium">In real life: </span>{d.real_world_example}</p>}
      {d.common_mistakes?.length > 0 && (
        <div className="text-sm"><p className="font-medium">Common interview mistakes</p><ul className="list-disc pl-5">{d.common_mistakes.map((x: string) => <li key={x}>{x}</li>)}</ul></div>
      )}
    </>
  );
}

function TwoLists({ a, b }: { a: [string, string[] | undefined]; b: [string, string[] | undefined] }) {
  return (
    <div className="grid gap-3 text-sm sm:grid-cols-2">
      {[a, b].map(([title, items]) => items && items.length > 0 && (
        <div key={title}><p className="font-medium">{title}</p><ul className="list-disc pl-5">{items.map((x) => <li key={x}>{x}</li>)}</ul></div>
      ))}
    </div>
  );
}

function References({ refs }: { refs?: Reference[] }) {
  if (!refs || refs.length === 0) return null;
  return (
    <div className="border-t border-border pt-2 text-xs text-muted">
      <p className="font-medium">Sources used</p>
      <ul>
        {refs.map((r, i) => (
          <li key={i}>
            [{r.n ?? i + 1}] {r.url ? <a href={r.url} target="_blank" rel="noreferrer noopener" className="underline">{r.title}</a> : r.title}
            {r.heading && ` — ${r.heading}`}
            {r.license && ` · ${r.license}`}
            {r.kind === "upload" && " · your notes"}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Recommendation({ m }: { m: CoachMessage }) {
  const d = m.data;
  return (
    <Bubble role="coach">
      <p className="text-sm font-medium">{m.content}</p>
      <div className="mt-2 space-y-1 text-sm text-muted">
        {d.weak_topics?.length > 0 && <p>Weakest topics: {d.weak_topics.map((w: { name: string; accuracy: number | null }) => `${w.name}${w.accuracy !== null ? ` (${Math.round(w.accuracy * 100)}%)` : ""}`).join(", ")}</p>}
        {d.lesson && <p>📖 Related lesson: <span className="text-foreground">{d.lesson.title}</span>{d.lesson.heading && ` — ${d.lesson.heading}`}</p>}
        <p>Next level for you: {d.next_difficulty_label}</p>
      </div>
    </Bubble>
  );
}

function Report({ m }: { m: CoachMessage }) {
  const d = m.data;
  return (
    <div className="space-y-4 rounded-lg border border-accent/40 bg-surface p-5">
      <h2 className="text-lg font-semibold">Interview report · {d.persona}</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Overall" value={`${d.overall_score}/100`} hint={d.verdict} />
        <Stat label="Questions" value={d.questions?.length ?? 0} />
        <Stat label="Follow-ups" value={(d.questions ?? []).filter((q: { follow_up: boolean }) => q.follow_up).length} />
      </div>
      <p className="whitespace-pre-wrap text-sm">{d.summary}</p>
      <BarList rows={Object.entries(d.criteria_averages ?? {}).map(([k, v]) => ({ key: k, label: k, value: Number(v) / 5 }))} format={(v) => `${(v * 5).toFixed(1)}/5`} />
      <TwoLists a={["Strengths", d.strengths]} b={["To improve", d.improvements]} />
      {d.next_steps?.length > 0 && <div className="text-sm"><p className="font-medium">Next steps</p><ol className="list-decimal pl-5">{d.next_steps.map((x: string) => <li key={x}>{x}</li>)}</ol></div>}
      <details className="text-sm">
        <summary className="cursor-pointer font-medium">Question-by-question feedback</summary>
        <ol className="mt-2 space-y-3">
          {(d.questions ?? []).map((q: { question: string; answer: string; score: number; feedback: string; follow_up: boolean }, i: number) => (
            <li key={i} className="rounded-md border border-border p-3">
              <p className="font-medium">{q.follow_up && "↳ "}{q.question} <span className="tabular-nums text-muted">· {q.score}/100</span></p>
              <p className="mt-1 text-muted">Your answer: {q.answer.slice(0, 300)}{q.answer.length > 300 && "…"}</p>
              <p className="mt-1">{q.feedback}</p>
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}

// --- inputs --------------------------------------------------------------------------------------------

function AnswerBox({ message, session, disabled, onAnswer, onHint, onReveal }: {
  message: CoachMessage;
  session: CoachSession;
  disabled: boolean;
  onAnswer: (body: { selected?: string[]; text?: string; language?: string }) => void;
  onHint: () => void;
  onReveal: () => void;
}) {
  const q = message.data.question ?? {};
  const options: { id: string; text: string }[] = q.options ?? [];
  const multi = q.type === "mcq_multi";
  const [selected, setSelected] = useState<string[]>([]);
  const [code, setCode] = useState<string>(message.data.starter_code ?? "");
  const [lang, setLang] = useState<CodeLanguage>("python");
  const hints = session.state.current?.hints ?? 0;

  const tools = (
    <div className="flex flex-wrap gap-2">
      {message.data.provenance !== "personal_capture" && hints < 3 && <button type="button" className={btn.ghost} onClick={onHint} disabled={disabled}>💡 Hint ({hints}/3)</button>}
      {session.learning_mode && <button type="button" className={btn.ghost} onClick={onReveal} disabled={disabled}>👁 Show the answer</button>}
    </div>
  );

  if (options.length > 0)
    return (
      <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (selected.length) onAnswer({ selected }); }}>
        <fieldset className="grid gap-2 sm:grid-cols-2">
          <legend className="sr-only">Your answer</legend>
          {options.map((o, i) => (
            <label key={o.id} className={`flex cursor-pointer items-start gap-2 rounded-md border p-2 text-sm ${selected.includes(o.id) ? "border-accent bg-accent/10" : "border-border"}`}>
              <input type={multi ? "checkbox" : "radio"} name="answer" checked={selected.includes(o.id)} onChange={() => setSelected(multi ? (selected.includes(o.id) ? selected.filter((x) => x !== o.id) : [...selected, o.id]) : [o.id])} />
              <span className="font-mono text-muted">{"ABCDEFGH"[i]}.</span>
              <span className="line-clamp-2">{o.text}</span>
            </label>
          ))}
        </fieldset>
        <div className="flex flex-wrap items-center justify-between gap-2">
          {tools}
          <button className={btn.primary} disabled={disabled || selected.length === 0}>Submit answer</button>
        </div>
      </form>
    );

  if (message.data.answer_format === "code")
    return (
      <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (code.trim()) onAnswer({ text: code, language: lang }); }}>
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor="lang">Language</label>
          <select id="lang" className={`${input} w-auto`} value={lang} onChange={(e) => setLang(e.target.value as CodeLanguage)}>
            {CODE_LANGUAGES.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        <CodeEditor value={code} onChange={setCode} language={lang} />
        <div className="flex flex-wrap items-center justify-between gap-2">
          {tools}
          <button className={btn.primary} disabled={disabled || !code.trim()}>Submit code</button>
        </div>
      </form>
    );

  return <TextAnswer disabled={disabled} onSubmit={(text) => onAnswer({ text })} tools={tools} placeholder="Write your answer. Structure it as you would in an interview." />;
}

function TextAnswer({ disabled, onSubmit, tools, placeholder }: { disabled: boolean; onSubmit: (text: string) => void; tools?: React.ReactNode; placeholder: string }) {
  const [text, setText] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    onSubmit(text);
    setText("");
  }
  return (
    <form className="space-y-2" onSubmit={submit}>
      <textarea aria-label="Your answer" className={`${input} min-h-28`} value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder}
        onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e); }} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        {tools ?? <span className="text-xs text-muted">Ctrl/⌘ + Enter to send</span>}
        <button className={btn.primary} disabled={disabled || !text.trim()}>Send answer</button>
      </div>
    </form>
  );
}

function AskTutor({ disabled, onAsk }: { disabled: boolean; onAsk: (message: string) => void }) {
  const [text, setText] = useState("");
  return (
    <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (text.trim()) { onAsk(text); setText(""); } }}>
      <label htmlFor="ask" className="sr-only">Ask the tutor</label>
      <input id="ask" className={input} value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask the tutor about a concept (it will not give the answer before you submit)…" />
      <button className={btn.secondary} disabled={disabled || !text.trim()}>Ask</button>
    </form>
  );
}
