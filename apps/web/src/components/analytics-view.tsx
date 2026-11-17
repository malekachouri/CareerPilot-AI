"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BarList, Card, Stat, formatDuration } from "@/components/ui";
import { api } from "@/lib/api/client";
import { DIFFICULTY_LABELS, type Analytics } from "@/lib/api/types";

export function AnalyticsView() {
  const [a, setA] = useState<Analytics | null>(null);

  useEffect(() => {
    api.GET("/api/v1/me/analytics").then(({ data }) => setA(data as unknown as Analytics));
  }, []);

  if (!a) return <p className="text-muted">Loading your statistics…</p>;
  if (a.answered === 0)
    return (
      <Card>
        <p>No graded answers yet. Take a test from the <Link className="text-accent underline" href="/tests">library</Link> to see your progress here.</p>
      </Card>
    );

  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Accuracy" value={a.accuracy !== null ? `${Math.round(a.accuracy * 100)}%` : "–"} hint={`${a.correct} correct of ${a.answered}`} />
        <Stat label="Incorrect answers" value={a.incorrect} />
        <Stat label="Avg. response time" value={formatDuration(a.average_response_time_ms)} />
        <Stat label="Tests taken" value={a.attempts} />
      </div>

      {a.knowledge_gaps.length > 0 && (
        <Card className="border-warn/50">
          <h2 className="mb-2 font-semibold">⚠ Knowledge gaps</h2>
          <p className="mb-3 text-sm text-muted">Topics with at least 5 graded answers and less than 60% accuracy.</p>
          <ul className="flex flex-wrap gap-2 text-sm" role="list">
            {a.knowledge_gaps.map((g) => (
              <li key={g.slug}>
                <Link href={`/tests?category=${g.slug}`} className="rounded-full border border-border px-3 py-1 hover:border-accent">
                  {g.name} · {Math.round(g.accuracy * 100)}%
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-1 font-semibold">Accuracy by topic</h2>
          <p className="mb-3 text-xs text-muted">Weakest first</p>
          <BarList rows={a.by_category.map((c) => ({ key: c.slug, label: c.name, value: c.accuracy, detail: `${c.correct}/${c.answered} correct, ${formatDuration(c.average_time_ms)} avg` }))} />
        </Card>
        <Card>
          <h2 className="mb-1 font-semibold">Accuracy by level</h2>
          <p className="mb-3 text-xs text-muted">Difficulty progression</p>
          <BarList rows={a.by_difficulty.map((d) => ({ key: String(d.difficulty), label: DIFFICULTY_LABELS[d.difficulty], value: d.accuracy, detail: `${d.answered} answered` }))} />
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 font-semibold">Test history</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-muted">
              <tr>
                <th className="py-1 pr-3 font-medium">Date</th>
                <th className="py-1 pr-3 font-medium">Test</th>
                <th className="py-1 pr-3 text-right font-medium">Score</th>
                <th className="py-1 text-right font-medium">Avg. level</th>
              </tr>
            </thead>
            <tbody>
              {[...a.timeline].reverse().map((t) => (
                <tr key={t.attempt_id} className="border-t border-border">
                  <td className="py-2 pr-3 tabular-nums text-muted">{t.submitted_at ? new Date(t.submitted_at).toLocaleDateString() : "–"}</td>
                  <td className="py-2 pr-3">
                    <Link className="hover:underline" href={`/attempts/${t.attempt_id}/results`}>{t.title}</Link>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{t.score_percent !== null ? `${t.score_percent}%` : "–"}</td>
                  <td className="py-2 text-right tabular-nums">{t.average_difficulty.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="mb-1 font-semibold">Repeated mistakes</h2>
        <p className="mb-3 text-xs text-muted">Questions you answered wrong at least twice</p>
        {a.repeated_mistakes.length === 0 ? (
          <p className="text-sm text-muted">None. Well done.</p>
        ) : (
          <ul className="space-y-2 text-sm" role="list">
            {a.repeated_mistakes.map((m) => (
              <li key={m.question_id} className="flex justify-between gap-4 border-t border-border pt-2">
                <span>{m.stem}</span>
                <span className="shrink-0 tabular-nums text-muted">✗ ×{m.times_wrong}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
