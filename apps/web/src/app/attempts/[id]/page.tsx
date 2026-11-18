import type { Metadata } from "next";
import { Suspense } from "react";

import { AttemptPlayer } from "@/components/attempt-player";

export const metadata: Metadata = { title: "Test in progress" };

export default function Page() {
  return (
    <>
      {/* Client data + URL params are request-time: render behind a Suspense boundary. */}
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <AttemptPlayer />
      </Suspense>
    </>
  );
}
