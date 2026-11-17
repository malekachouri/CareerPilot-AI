import type { Metadata } from "next";
import { Suspense } from "react";

import { CompanyView } from "@/components/companies";

export const metadata: Metadata = { title: "Company" };

export default function Page() {
  return (
    <>
      {/* Client data + URL params are request-time: render behind a Suspense boundary. */}
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <CompanyView />
      </Suspense>
    </>
  );
}
