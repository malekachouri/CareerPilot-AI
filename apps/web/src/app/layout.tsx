import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "CareerPilot AI", template: "%s · CareerPilot AI" },
  description: "Interview preparation, English and job discovery — free, open source and self-hosted.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <header className="border-b border-border bg-surface">
          <nav className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-3">
            <Link href="/" className="font-semibold tracking-tight">
              CareerPilot <span className="text-accent">AI</span>
            </Link>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
              {[
                ["/tests", "Tests"],
                ["/coach", "Coach"],
                ["/companies", "Companies"],
                ["/generate", "Generate"],
                ["/analytics", "Analytics"],
                ["/dashboard", "Dashboard"],
              ].map(([href, label]) => (
                <Link key={href} href={href} className="text-muted hover:text-foreground">
                  {label}
                </Link>
              ))}
            </div>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">{children}</main>
        <footer className="border-t border-border py-6 text-center text-xs text-muted">
          Open source · self-hosted · runs on local models
        </footer>
      </body>
    </html>
  );
}
