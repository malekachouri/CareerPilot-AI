import type { Metadata } from "next";
import { Suspense } from "react";

import { CompaniesList } from "@/components/companies";
import { PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Companies" };

export default function Page() {
  return (
    <>
      <PageHeader title="Company preparation">Your private notes from tests you took, and practice collections inspired by publicly documented recruitment topics. Nothing here is presented as a real company test.</PageHeader>
      {/* Client data + URL params are request-time: render behind a Suspense boundary. */}
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <CompaniesList />
      </Suspense>
    </>
  );
}
