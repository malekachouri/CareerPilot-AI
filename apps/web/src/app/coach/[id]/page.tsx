import type { Metadata } from "next";
import { Suspense } from "react";

import { CoachChat } from "@/components/coach-chat";

export const metadata: Metadata = { title: "Coach session" };

export default function Page() {
  return (
    <Suspense fallback={<p className="text-muted">Loading…</p>}>
      <CoachChat />
    </Suspense>
  );
}
