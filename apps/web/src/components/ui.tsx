import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

export const btn = {
  primary:
    "inline-flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:opacity-90 disabled:opacity-50",
  secondary:
    "inline-flex items-center justify-center gap-2 rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium hover:bg-background disabled:opacity-50",
  ghost: "inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-muted hover:text-foreground",
};

export const input =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/30";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-lg border border-border bg-surface p-4 ${className}`}>{children}</div>;
}

export function Badge({ children, tone = "neutral", title }: { children: ReactNode; tone?: "neutral" | "accent" | "warn"; title?: string }) {
  const tones = {
    neutral: "border-border text-muted",
    accent: "border-accent/40 text-accent",
    warn: "border-warn/50 text-warn",
  };
  return (
    <span title={title} className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

const PROVENANCE: Record<string, { label: string; tone: "neutral" | "accent" | "warn"; title: string }> = {
  original: { label: "CareerPilot original", tone: "accent", title: "Written for CareerPilot, reviewed" },
  community_licensed: { label: "Open resource", tone: "neutral", title: "Reused under the source licence, with attribution" },
  official_public: { label: "Official practice", tone: "accent", title: "Published by the organisation itself" },
  ai_generated: { label: "AI-generated · unverified", tone: "warn", title: "Created by the local model. It may contain errors." },
  user_created: { label: "Created by you", tone: "neutral", title: "Your own question" },
  personal_capture: { label: "Your private notes", tone: "neutral", title: "Visible only to you, never shared" },
};

export function ProvenanceBadge({ provenance }: { provenance: string }) {
  const p = PROVENANCE[provenance] ?? { label: provenance, tone: "neutral" as const, title: provenance };
  return (
    <Badge tone={p.tone} title={p.title}>
      {p.label}
    </Badge>
  );
}

export function PageHeader({ title, children, back }: { title: string; children?: ReactNode; back?: { href: ComponentProps<typeof Link>["href"]; label: string } }) {
  return (
    <div className="mb-6 space-y-2">
      {back && (
        <Link href={back.href} className="text-sm text-muted hover:text-foreground">
          ← {back.label}
        </Link>
      )}
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      {children && <div className="text-sm text-muted">{children}</div>}
    </div>
  );
}

/** Single-series horizontal bars: one hue, value printed in text ink next to each bar (no legend needed). */
export function BarList({ rows, format = (v) => `${Math.round(v * 100)}%` }: {
  rows: { key: string; label: string; value: number; detail?: string }[];
  format?: (v: number) => string;
}) {
  if (rows.length === 0) return <p className="text-sm text-muted">No data yet.</p>;
  return (
    <ul className="space-y-2" role="list">
      {rows.map((r) => (
        <li key={r.key} className="grid grid-cols-[minmax(8rem,14rem)_1fr_4.5rem] items-center gap-3 text-sm" title={`${r.label}: ${format(r.value)}${r.detail ? ` · ${r.detail}` : ""}`}>
          <span className="truncate">{r.label}</span>
          <span className="h-2.5 rounded-full bg-border/60" aria-hidden>
            <span className="block h-2.5 rounded-full bg-chart" style={{ width: `${Math.max(2, Math.min(100, r.value * 100))}%` }} />
          </span>
          <span className="text-right tabular-nums text-muted">
            {format(r.value)}
            {r.detail && <span className="sr-only"> ({r.detail})</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

/** Correct / incorrect / not graded: always icon + text, never colour alone. */
export function Verdict({ value }: { value: boolean | null }) {
  if (value === true) return <span className="font-medium text-good">✓ Correct</span>;
  if (value === false) return <span className="font-medium text-critical">✗ Incorrect</span>;
  return <span className="font-medium text-muted">○ Not auto-graded</span>;
}

export function formatDuration(ms: number | null | undefined): string {
  if (!ms) return "–";
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}
