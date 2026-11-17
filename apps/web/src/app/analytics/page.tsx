import type { Metadata } from "next";
import { Suspense } from "react";

import { AnalyticsView } from "@/components/analytics-view";
import { PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "My progress" };

export default function Page() {
  return (
    <>
      <PageHeader title="My progress">Accuracy by topic and level, response time, repeated mistakes and knowledge gaps.</PageHeader>
      {/* Client data + URL params are request-time: render behind a Suspense boundary. */}
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <AnalyticsView />
      </Suspense>
    </>
  );
}
