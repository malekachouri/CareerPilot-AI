import type { Metadata } from "next";
import { Suspense } from "react";

import { AttemptResultsView } from "@/components/attempt-results";

export const metadata: Metadata = { title: "Results" };

export default function Page() {
  return (
    <>
      {/* Client data + URL params are request-time: render behind a Suspense boundary. */}
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <AttemptResultsView />
      </Suspense>
    </>
  );
}
