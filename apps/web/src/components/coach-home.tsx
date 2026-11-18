"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Badge, Card, btn, input } from "@/components/ui";
import { coach } from "@/lib/api/coach";
import type { AgentInfo, InterviewInfo, LearningProfile, SessionSummary } from "@/lib/api/coach-types";

type Status = { llm: { provider: string; model: string; available: boolean }; embeddings: { provider: string; model: string } };

export function CoachHome() {
  const router = useRouter();
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [interviews, setInterviews] = useState<InterviewInfo[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [learning, setLearning] = useState(false);
  const [minutes, setMinutes] = useState(30);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    coach<{ agents: AgentInfo[]; interviews: InterviewInfo[] }>("/coach/agents").then(({ data }) => {
      setAgents(data?.agents ?? []);
      setInterviews(data?.interviews ?? []);
    });
    coach<SessionSummary[]>("/coach/sessions").then(({ data }) => setSessions(data ?? []));
    coach<Status>("/coach/status").then(({ data }) => setStatus(data ?? null));
    coach<LearningProfile>("/me/learning-profile").then(({ data }) => data && setMinutes(data.interview_minutes));
  }, []);

  async function start(path: string, body: unknown, key: string) {
    setBusy(key);
    setError(null);
    const { data, error } = await coach<{ id: string }>(path, { method: "POST", body });
    setBusy(null);
    if (error || !data) return setError(error ?? "Could not start");
    router.push(`/coach/${data.id}`);
  }

  return (
    <div className="space-y-10">
      {status && !status.llm.available && (
        <Card className="border-warn/50 text-sm">
          <p className="font-medium text-warn">⚠ Local model not available ({status.llm.provider} · {status.llm.model})</p>
          <p className="mt-1 text-muted">
            Multiple-choice coaching still works (grading, stored explanations, recommendations). Explanations by the AI, open
            answers, interviews, hints and the tutor chat need the model: <code className="font-mono">docker compose --profile ai up -d</code>,
            then <code className="font-mono">docker compose exec ollama ollama pull {status.llm.model}</code> and{" "}
            <code className="font-mono">ollama pull {status.embeddings.model}</code>.
          </p>
        </Card>
      )}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Practise with a specialised coach</h2>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={learning} onChange={(e) => setLearning(e.target.checked)} />
            Learning mode (answers can be revealed before you submit)
          </label>
        </div>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="list">
          {agents.map((a) => (
            <li key={a.slug}>
              <button
                onClick={() => start("/coach/sessions", { agent: a.slug, learning_mode: learning }, a.slug)}
                disabled={busy !== null}
                className="h-full w-full rounded-lg border border-border bg-surface p-4 text-left hover:border-accent disabled:opacity-60"
              >
                <p className="font-medium">{a.name}</p>
                <p className="mt-1 text-sm text-muted">{a.description}</p>
                {a.disclaimer && <p className="mt-2 text-xs text-muted">{a.disclaimer}</p>}
                <p className="mt-2 text-xs text-accent">{busy === a.slug ? "Starting…" : a.answer_format === "code" ? "Code editor →" : "Start →"}</p>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Interview simulations</h2>
          <label className="flex items-center gap-2 text-sm">
            Duration
            <select className={`${input} w-auto`} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}>
              {[15, 20, 30, 45, 60].map((m) => <option key={m} value={m}>{m} min</option>)}
            </select>
          </label>
        </div>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="list">
          {interviews.map((i) => (
            <li key={i.slug}>
              <button
                onClick={() => start("/coach/interviews", { persona: i.slug, duration_minutes: minutes }, i.slug)}
                disabled={busy !== null || status?.llm.available === false}
                className="h-full w-full rounded-lg border border-border bg-surface p-4 text-left hover:border-accent disabled:opacity-60"
              >
                <p className="font-medium">{i.name}</p>
                <p className="mt-1 text-sm text-muted">{i.description}</p>
                <p className="mt-2 text-xs text-accent">{busy === i.slug ? "Starting…" : "One question at a time · report at the end →"}</p>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-semibold">Conversation history</h2>
          {sessions.length === 0 ? (
            <p className="text-sm text-muted">No session yet.</p>
          ) : (
            <ul className="divide-y divide-border text-sm" role="list">
              {sessions.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-2 py-2">
                  <Link href={`/coach/${s.id}`} className="hover:underline">{s.title}</Link>
                  <span className="flex shrink-0 items-center gap-2 text-xs text-muted">
                    {s.overall_score !== null && <span className="tabular-nums">{s.overall_score}/100</span>}
                    <Badge>{s.status === "ended" ? "Ended" : s.kind === "interview" ? "Interview" : "Practice"}</Badge>
                    {new Date(s.updated_at).toLocaleDateString()}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <div className="space-y-6">
          <ProfileForm />
          <Materials />
        </div>
      </div>
    </div>
  );
}

function ProfileForm() {
  const [p, setP] = useState<LearningProfile | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    coach<LearningProfile>("/me/learning-profile").then(({ data }) => setP(data ?? null));
  }, []);
  if (!p) return null;
  async function save(e: FormEvent) {
    e.preventDefault();
    const { error } = await coach("/me/learning-profile", { method: "PUT", body: p });
    setSaved(!error);
  }
  return (
    <Card>
      <form onSubmit={save} className="space-y-3 text-sm">
        <h2 className="font-semibold">My learning profile</h2>
        <p className="text-muted">Used to adapt questions, interview length and difficulty. Your topic levels come from every answer you give.</p>
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="font-medium">Target role</span>
            <input className={input} value={p.target_role} onChange={(e) => setP({ ...p, target_role: e.target.value })} />
          </label>
          <label className="space-y-1">
            <span className="font-medium">Level</span>
            <select className={input} value={p.seniority} onChange={(e) => setP({ ...p, seniority: e.target.value as LearningProfile["seniority"] })}>
              <option value="junior">Junior</option>
              <option value="mid">Mid-level</option>
              <option value="senior">Senior</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="font-medium">Interview length (min)</span>
            <input type="number" min={10} max={90} className={input} value={p.interview_minutes} onChange={(e) => setP({ ...p, interview_minutes: Number(e.target.value) })} />
          </label>
        </div>
        <button className={btn.secondary}>Save</button>
        {saved && <span role="status" className="ml-2 text-good">✓ Saved</span>}
      </form>
    </Card>
  );
}

function Materials() {
  const [docs, setDocs] = useState<{ id: string; title: string }[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => coach<{ id: string; title: string }[]>("/me/kb").then(({ data }) => setDocs(data ?? []));
  useEffect(() => {
    load();
  }, []);
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const file = (e.currentTarget.elements.namedItem("file") as HTMLInputElement).files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    const { readCookie } = await import("@/lib/api/client");
    const res = await fetch("/api/v1/me/kb/upload", { method: "POST", body: form, headers: { "X-CSRF-Token": readCookie("cp_csrf") ?? "" } });
    setMsg(res.ok ? "✓ Added: your coach can now cite it." : "Upload failed.");
    load();
  }
  return (
    <Card>
      <form onSubmit={upload} className="space-y-3 text-sm">
        <h2 className="font-semibold">My learning materials</h2>
        <p className="text-muted">Markdown, text or PDF notes. Private to you; the coach searches them and cites them as sources.</p>
        <input name="file" type="file" accept=".md,.txt,.pdf" required className="block w-full" />
        <button className={btn.secondary}>Upload</button>
        {msg && <p role="status">{msg}</p>}
        {docs.length > 0 && (
          <ul className="list-disc pl-5 text-muted">
            {docs.map((d) => <li key={d.id}>{d.title}</li>)}
          </ul>
        )}
      </form>
    </Card>
  );
}
