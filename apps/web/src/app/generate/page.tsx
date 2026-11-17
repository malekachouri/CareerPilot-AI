import type { Metadata } from "next";
import { Suspense } from "react";

import { Generator } from "@/components/generator";
import { PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Question generator" };

export default function Page() {
  return (
    <>
      <PageHeader title="AI question generator">Generate practice questions with the local model. They are stored separately from verified questions.</PageHeader>
      {/* Client data + URL params are request-time: render behind a Suspense boundary. */}
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <Generator />
      </Suspense>
    </>
  );
}
