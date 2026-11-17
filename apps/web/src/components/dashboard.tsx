"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, type User } from "@/lib/api/client";

export function Dashboard() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.GET("/api/v1/me").then(({ data, response }) => {
      if (cancelled) return;
      if (response.status === 401 || !data) {
        router.replace("/login?next=/dashboard");
        return;
      }
      setUser(data);
    });
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function logout() {
    await api.POST("/api/v1/auth/logout");
    // Full navigation on purpose: drops the client router cache, which holds pages rendered while logged in.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/login");
  }

  if (!user) {
    return <p className="text-muted">Loading your dashboard…</p>;
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Welcome, {user.display_name}</h1>
          <p className="text-sm text-muted">
            {user.email} · role <span className="font-medium text-foreground">{user.role}</span>
          </p>
        </div>
        <button
          type="button"
          onClick={logout}
          className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-surface"
        >
          Log out
        </button>
      </div>
      <section className="grid gap-4 sm:grid-cols-2">
        {[
          ["/tests", "Interview Tests Hub", "Curated tests, a custom test builder and your private test notes."],
          ["/analytics", "My progress", "Accuracy by topic, response time, repeated mistakes and gaps."],
          ["/companies", "Company preparation", "Your private collections and practice by company."],
          ["/generate", "AI question generator", "Generate practice questions with the local model."],
        ].map(([href, title, text]) => (
          <Link key={href} href={href} className="rounded-lg border border-border bg-surface p-5 hover:border-accent">
            <p className="font-semibold">{title}</p>
            <p className="mt-1 text-sm text-muted">{text}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
