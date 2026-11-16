import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = { title: "Log in" };

export default function LoginPage() {
  return (
    <div className="mx-auto max-w-sm space-y-6">
      <h1 className="text-2xl font-bold">Log in</h1>
      {/* useSearchParams (for ?next=) is request-time data: it must sit behind a Suspense boundary. */}
      <Suspense>
        <AuthForm mode="login" />
      </Suspense>
    </div>
  );
}
