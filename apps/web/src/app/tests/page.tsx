import type { Metadata } from "next";
import { Suspense } from "react";

import { TestsLibrary } from "@/components/tests-library";
import { PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Test library" };

export default function Page() {
  return (
    <>
      <PageHeader title="Interview Tests Hub">Curated tests, your custom and AI-generated tests, and your private collections. Every question shows where it comes from.</PageHeader>
      {/* Client data + URL params are request-time: render behind a Suspense boundary. */}
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <TestsLibrary />
      </Suspense>
    </>
  );
}
