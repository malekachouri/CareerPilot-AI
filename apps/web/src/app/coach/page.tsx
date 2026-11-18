import type { Metadata } from "next";
import { Suspense } from "react";

import { CoachHome } from "@/components/coach-home";
import { PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "AI Interview Coach" };

export default function Page() {
  return (
    <>
      <PageHeader title="AI Interview Coach">
        Specialised coaches explain, evaluate and adapt to your level. Interview simulations ask one question at a time and
        end with a detailed report. Everything runs on your local model.
      </PageHeader>
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <CoachHome />
      </Suspense>
    </>
  );
}
