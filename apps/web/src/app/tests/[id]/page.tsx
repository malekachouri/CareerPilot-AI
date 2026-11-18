import type { Metadata } from "next";
import { Suspense } from "react";

import { TestDetail } from "@/components/test-detail";

export const metadata: Metadata = { title: "Test" };

export default function Page() {
  return (
    <>
      {/* Client data + URL params are request-time: render behind a Suspense boundary. */}
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <TestDetail />
      </Suspense>
    </>
  );
}
