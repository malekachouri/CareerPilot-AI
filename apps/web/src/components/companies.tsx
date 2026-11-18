"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, Card, PageHeader, ProvenanceBadge } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { Company, CompanyDetail, TestSummary } from "@/lib/api/types";

export function CompaniesList() {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  useEffect(() => {
    api.GET("/api/v1/companies").then(({ data }) => setCompanies(data ?? []));
  }, []);
  if (!companies) return <p className="text-muted">Loading…</p>;
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="list">
      {companies.map((c) => (
        <li key={c.slug}>
          <Link href={`/companies/${c.slug}`} className="block rounded-lg border border-border bg-surface p-4 hover:border-accent">
            <p className="font-medium">{c.name}</p>
            <p className="mt-1 text-xs text-muted">
              {c.tests} collection(s) · {c.public_questions} practice question(s)
              {c.my_private_questions > 0 && ` · ${c.my_private_questions} private note(s)`}
            </p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function CompanyView() {
  const { slug } = useParams<{ slug: string }>();
  const [company, setCompany] = useState<CompanyDetail | null>(null);
  const [tests, setTests] = useState<TestSummary[]>([]);
  useEffect(() => {
    api.GET("/api/v1/companies/{slug}", { params: { path: { slug } } }).then(({ data }) => setCompany(data ?? null));
    api.GET("/api/v1/tests", { params: { query: { company: slug } } }).then(({ data }) => setTests(data ?? []));
  }, [slug]);
  if (!company) return <p className="text-muted">Loading…</p>;
  return (
    <div className="space-y-6">
      <PageHeader title={`${company.name} preparation`} back={{ href: "/companies", label: "Companies" }}>
        {company.website && (
          <a href={company.website} className="underline" target="_blank" rel="noreferrer noopener">
            {company.website}
          </a>
        )}
      </PageHeader>
      <p className="rounded-md border border-border bg-surface p-3 text-sm">{company.disclaimer}</p>
      <Card>
        <h2 className="mb-2 font-semibold">Official preparation resources</h2>
        {company.official_prep_links.length ? (
          <ul className="list-disc pl-5 text-sm">
            {company.official_prep_links.map((l) => (
              <li key={l}><a className="underline" href={l} target="_blank" rel="noreferrer noopener">{l}</a></li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">None reviewed yet. Links are added only after checking the company&apos;s own pages.</p>
        )}
      </Card>
      <section className="space-y-3">
        <h2 className="font-semibold">Collections</h2>
        {tests.length === 0 && <p className="text-sm text-muted">No collection for this company yet.</p>}
        {tests.map((t) => (
          <Link key={t.id} href={`/tests/${t.id}`} className="block rounded-lg border border-border bg-surface p-4 hover:border-accent">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium">{t.title}</p>
              <div className="flex gap-1">
                {t.visibility === "private" && <Badge>Private</Badge>}
                {t.provenance.map((p) => <ProvenanceBadge key={p} provenance={p} />)}
              </div>
            </div>
            {t.label && <p className="mt-1 text-xs text-muted">{t.label}</p>}
            <p className="mt-1 text-xs text-muted">{t.question_count} questions</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
