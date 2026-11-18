"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { Badge, Card, ProvenanceBadge, btn, input } from "@/components/ui";
import { api, problemMessage } from "@/lib/api/client";
import { DIFFICULTY_LABELS, type Category, type TestSummary } from "@/lib/api/types";

const KINDS: Record<string, string> = {
  curated: "Curated",
  custom: "My custom tests",
  generated: "AI-generated",
  company: "Company collections",
};

export function TestsLibrary() {
  const [tests, setTests] = useState<TestSummary[] | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [q, setQ] = useState("");
  const params = useSearchParams();
  const [category, setCategory] = useState(params.get("category") ?? "");
  const [difficulty, setDifficulty] = useState("");
  const [kind, setKind] = useState("");

  useEffect(() => {
    api.GET("/api/v1/categories").then(({ data }) => setCategories(data ?? []));
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .GET("/api/v1/tests", {
          params: {
            query: {
              q: q || undefined,
              category: category || undefined,
              difficulty: difficulty ? Number(difficulty) : undefined,
              kind: kind || undefined,
            },
          },
        })
        .then(({ data }) => setTests(data ?? []));
    }, 200);
    return () => clearTimeout(t);
  }, [q, category, difficulty, kind]);

  return (
    <div className="space-y-8">
      <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_1fr]" role="search">
        <label className="sr-only" htmlFor="search">Search tests</label>
        <input id="search" className={input} placeholder="Search tests…" value={q} onChange={(e) => setQ(e.target.value)} />
        <CategorySelect categories={categories} value={category} onChange={setCategory} label="All topics" />
        <select aria-label="Difficulty" className={input} value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
          <option value="">Any level</option>
          {Object.entries(DIFFICULTY_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <select aria-label="Kind" className={input} value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">All tests</option>
          {Object.entries(KINDS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>

      {tests === null ? (
        <p className="text-muted">Loading tests…</p>
      ) : tests.length === 0 ? (
        <p className="text-muted">No test matches these filters.</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2" role="list">
          {tests.map((t) => (
            <li key={t.id}>
              <TestCard test={t} />
            </li>
          ))}
        </ul>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <CustomTestBuilder categories={categories} />
        <UploadQuestions categories={categories} />
      </div>
    </div>
  );
}

export function CategorySelect({ categories, value, onChange, label, id, allowGroups = true }: {
  categories: Category[];
  value: string;
  onChange: (v: string) => void;
  label: string;
  id?: string;
  allowGroups?: boolean;
}) {
  return (
    <select id={id} aria-label={label} className={input} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{label}</option>
      {categories.map((g) => (
        <optgroup key={g.slug} label={g.name}>
          {allowGroups && <option value={g.slug}>All {g.name}</option>}
          {(g.children ?? []).map((c) => (
            <option key={c.slug} value={c.slug}>{c.name}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

function TestCard({ test }: { test: TestSummary }) {
  return (
    <Link href={`/tests/${test.id}`} className="block h-full rounded-lg border border-border bg-surface p-4 transition hover:border-accent">
      <div className="flex items-start justify-between gap-3">
        <p className="font-medium">{test.title}</p>
        <Badge>{KINDS[test.kind] ?? test.kind}</Badge>
      </div>
      {test.description && <p className="mt-1 line-clamp-2 text-sm text-muted">{test.description}</p>}
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted">
        <span>{test.question_count} questions</span>
        <span>·</span>
        <span>{test.time_limit_s ? `${Math.round(test.time_limit_s / 60)} min` : "Untimed"}</span>
        {test.average_difficulty && (
          <>
            <span>·</span>
            <span>{DIFFICULTY_LABELS[Math.round(test.average_difficulty)]}</span>
          </>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-1">
        {test.provenance.map((p) => (
          <ProvenanceBadge key={p} provenance={p} />
        ))}
        {test.company && <Badge>{test.company.name}</Badge>}
      </div>
    </Link>
  );
}

function CustomTestBuilder({ categories }: { categories: Category[] }) {
  const router = useRouter();
  const [selected, setSelected] = useState<string[]>([]);
  const [levels, setLevels] = useState<number[]>([]);
  const [count, setCount] = useState(10);
  const [minutes, setMinutes] = useState<number | "">(15);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const flat = useMemo(() => categories.flatMap((g) => g.children ?? []), [categories]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    const { data, error } = await api.POST("/api/v1/tests/custom", {
      body: {
        title: selected.length ? `Custom: ${selected.map((s) => flat.find((c) => c.slug === s)?.name ?? s).join(", ")}` : "Custom mixed test",
        categories: selected,
        difficulties: levels,
        count,
        time_limit_minutes: minutes === "" ? null : minutes,
        mode: "exam",
        require_key: true,
      },
    });
    setPending(false);
    if (error || !data) return setError(problemMessage(error));
    router.push(`/tests/${data.id}`);
  }

  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  return (
    <Card>
      <form onSubmit={submit} className="space-y-4">
        <h2 className="font-semibold">Build a custom test</h2>
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Topics (none = all)</legend>
          <div className="max-h-48 space-y-2 overflow-y-auto pr-1">
            {categories.map((g) => (
              <div key={g.slug}>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">{g.name}</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {(g.children ?? []).map((c) => (
                    <button
                      type="button"
                      key={c.slug}
                      aria-pressed={selected.includes(c.slug)}
                      onClick={() => setSelected(toggle(selected, c.slug))}
                      className={`rounded-full border px-2 py-0.5 text-xs ${selected.includes(c.slug) ? "border-accent bg-accent text-accent-foreground" : "border-border hover:border-accent"}`}
                    >
                      {c.name}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Levels (none = all)</legend>
          <div className="flex flex-wrap gap-3 text-sm">
            {Object.entries(DIFFICULTY_LABELS).map(([v, l]) => (
              <label key={v} className="flex items-center gap-1">
                <input type="checkbox" checked={levels.includes(Number(v))} onChange={() => setLevels(toggle(levels, Number(v)))} />
                {l}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <label className="space-y-1">
            <span className="font-medium">Questions</span>
            <input type="number" min={1} max={100} className={input} value={count} onChange={(e) => setCount(Number(e.target.value))} />
          </label>
          <label className="space-y-1">
            <span className="font-medium">Minutes (empty = untimed)</span>
            <input type="number" min={1} max={300} className={input} value={minutes} onChange={(e) => setMinutes(e.target.value === "" ? "" : Number(e.target.value))} />
          </label>
        </div>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <button className={btn.primary} disabled={pending}>{pending ? "Building…" : "Create test"}</button>
      </form>
    </Card>
  );
}

function UploadQuestions({ categories }: { categories: Category[] }) {
  const [kind, setKind] = useState("user_created");
  const [category, setCategory] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const file = (e.currentTarget.elements.namedItem("file") as HTMLInputElement).files?.[0];
    if (!file) return;
    setPending(true);
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    form.append("category", category);
    const { readCookie } = await import("@/lib/api/client");
    const res = await fetch("/api/v1/me/imports/upload", {
      method: "POST",
      body: form,
      headers: { "X-CSRF-Token": readCookie("cp_csrf") ?? "" },
    });
    const body = await res.json();
    setPending(false);
    setMessage(
      res.ok
        ? `Imported ${body.created} question(s). ${body.duplicates + body.near_duplicates} duplicate(s) skipped, ${body.error_count} problem(s).`
        : problemMessage(body),
    );
  }

  return (
    <Card>
      <form onSubmit={submit} className="space-y-4">
        <h2 className="font-semibold">Import my questions</h2>
        <p className="text-sm text-muted">
          JSON, YAML, CSV, Markdown (task lists) or PDF. Imported questions stay <strong>private to you</strong>.
        </p>
        <input name="file" type="file" required accept=".json,.yaml,.yml,.csv,.md,.txt,.pdf" className="block w-full text-sm" />
        <div className="grid grid-cols-2 gap-3">
          <select aria-label="Kind of content" className={input} value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="user_created">My own questions</option>
            <option value="personal_capture">Notes from a test I took</option>
          </select>
          <CategorySelect categories={categories} value={category} onChange={setCategory} label="Default topic" />
        </div>
        {message && <p role="status" className="text-sm">{message}</p>}
        <button className={btn.secondary} disabled={pending}>{pending ? "Importing…" : "Import"}</button>
      </form>
    </Card>
  );
}
