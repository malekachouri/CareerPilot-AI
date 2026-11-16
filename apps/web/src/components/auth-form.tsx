"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { api, problemMessage } from "@/lib/api/client";

type Mode = "login" | "register";

/** Only allow same-site relative redirects after login (prevents open redirects via ?next=). */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

export function AuthForm({ mode }: { mode: Mode }) {
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    const result =
      mode === "login"
        ? await api.POST("/api/v1/auth/login", { body: { email, password } })
        : await api.POST("/api/v1/auth/register", {
            body: { email, password, display_name: String(form.get("display_name") ?? ""), locale: "en" },
          });
    setPending(false);
    if (result.error) {
      setError(problemMessage(result.error));
      return;
    }
    // Full navigation, not router.replace: routes prefetched while logged out (e.g. the redirect from
    // /dashboard to /login) are cached client-side and must not be reused once a session exists.
    window.location.assign(safeNext(params.get("next")));
  }

  const isRegister = mode === "register";
  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      {isRegister && (
        <Field label="Name" name="display_name" autoComplete="name" required maxLength={80} />
      )}
      <Field label="Email" name="email" type="email" autoComplete="email" required />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete={isRegister ? "new-password" : "current-password"}
        required
        minLength={isRegister ? 12 : undefined}
        hint={isRegister ? "At least 12 characters. A passphrase works well." : undefined}
      />
      {error && (
        <p role="alert" className="rounded-md border border-danger/40 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-md bg-accent px-4 py-2 font-medium text-accent-foreground hover:opacity-90 disabled:opacity-60"
      >
        {pending ? "Please wait…" : isRegister ? "Create account" : "Log in"}
      </button>
      <p className="text-center text-sm text-muted">
        {isRegister ? (
          <>
            Already have an account? <Link href="/login" className="text-accent underline">Log in</Link>
          </>
        ) : (
          <>
            New here? <Link href="/register" className="text-accent underline">Create an account</Link>
          </>
        )}
      </p>
    </form>
  );
}

function Field({
  label,
  name,
  hint,
  ...input
}: { label: string; name: string; hint?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  const id = `field-${name}`;
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        name={name}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="w-full rounded-md border border-border bg-surface px-3 py-2 outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
        {...input}
      />
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
